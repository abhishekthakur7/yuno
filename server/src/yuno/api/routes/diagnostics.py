"""Persisted diagnostic/setup HTTP API (IDK-105)."""

from __future__ import annotations

from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, status

from yuno.api.contracts import (
    DiagnosticAnswerRequest,
    DiagnosticAnswerResponse,
    DiagnosticCreateRequest,
    DiagnosticPatchRequest,
    DiagnosticQuestionResponse,
    DiagnosticResponse,
    DiagnosticRoadmapPreviewResponse,
    DiagnosticRoadmapPreviewUpdateRequest,
    GoalResponse,
)
from yuno.api.dependencies import (
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
    if_match,
    parse_if_match,
)
from yuno.modules.canonical.domain import RelationType
from yuno.modules.diagnostics.domain import (
    DiagnosticAnswer,
    DiagnosticSession,
    DiagnosticsIdempotencyRecord,
    DiagnosticState,
    next_question,
)
from yuno.modules.diagnostics.ports import DiagnosticsUnitOfWork
from yuno.modules.diagnostics.service import (
    append_diagnostic_answer,
    create_diagnostic,
    get_diagnostic,
    patch_diagnostic,
    record_diagnostic_failure,
    replace_roadmap_preview_edits,
)
from yuno.modules.profiles_goals.domain import (
    GoalPath,
    TargetCapability,
    TargetLevel,
)
from yuno.modules.profiles_goals.service import create_goal
from yuno.modules.roadmap.domain import (
    CorrectionType,
    LearnerCorrection,
    LearningClassification,
    LearningState,
    OverlayEntry,
    OverlayEntryType,
    RoadmapRelation,
    RoadmapTopic,
    project_roadmap,
)
from yuno.modules.roadmap.ports import RoadmapUnitOfWork
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    GoneError,
    IdempotencyConflictError,
    UnavailableError,
    YunoError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["diagnostics"])


class DiagnosticsApiUnitOfWork(DiagnosticsUnitOfWork, RoadmapUnitOfWork, Protocol):
    """Repositories needed by the cross-module diagnostic HTTP workflow."""


@router.get("/diagnostics/active", response_model=DiagnosticResponse | None)
def get_active_diagnostic_session(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsApiUnitOfWork, Depends(get_unit_of_work)],
) -> DiagnosticResponse | None:
    """Return the server-persisted onboarding session, if one exists.

    The client deliberately keeps no diagnostic identifier in browser
    storage. A cleared browser therefore resumes from the same durable
    server state instead of silently starting another onboarding flow.
    """
    session = uow.diagnostics.get_latest_unconfirmed_session(owner_id)
    if session is None:
        return None
    try:
        return _diagnostic_response(uow, get_diagnostic(uow, owner_id, session.id))
    except GoneError:
        return None


@router.post(
    "/diagnostics",
    response_model=DiagnosticResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_diagnostic(
    body: DiagnosticCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsApiUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> DiagnosticResponse:
    uow.diagnostics.lock_idempotency_commands(owner_id)
    request_hash = hash_payload(body.model_dump(mode="json"))
    prior = uow.diagnostics.get_idempotency(owner_id, "create_diagnostic", key)
    if prior is not None:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different diagnostic request."
            )
        return DiagnosticResponse.model_validate_json(prior.response_json)
    setup_inputs = dict(body.setup_inputs)
    setup_inputs.update(
        {
            "path": body.path.value,
            "subject": body.subject,
            "role": body.role,
            "target_level": body.target_level.value,
            "target_capability": body.target_capability.value,
        }
    )
    session = create_diagnostic(
        uow,
        owner_id,
        captured_graph_version_id=body.graph_version_id,
        setup_inputs=setup_inputs,
        approved_graph_exists=(
            uow.canonical.get_published_version(body.graph_version_id) is not None
        ),
    )
    response = _diagnostic_response(uow, session)
    uow.diagnostics.add_idempotency(
        DiagnosticsIdempotencyRecord(
            id=new_id(),
            owner_id=owner_id,
            operation="create_diagnostic",
            idempotency_key=key,
            request_hash=request_hash,
            session_id=session.id,
            response_json=response.model_dump_json(),
            created_at=now_text(SystemClock()),
        )
    )
    uow.commit()
    return response


@router.get("/diagnostics/{session_id}", response_model=DiagnosticResponse)
def get_diagnostic_session(
    session_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsApiUnitOfWork, Depends(get_unit_of_work)],
) -> DiagnosticResponse:
    return _diagnostic_response(uow, get_diagnostic(uow, owner_id, session_id))


@router.patch("/diagnostics/{session_id}", response_model=DiagnosticResponse)
def update_diagnostic_session(
    session_id: str,
    body: DiagnosticPatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsApiUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
) -> DiagnosticResponse:
    uow.diagnostics.lock_idempotency_commands(owner_id)
    supplied = "untrusted_seed_text" in body.model_fields_set
    try:
        session = patch_diagnostic(
            uow,
            owner_id,
            session_id,
            parse_if_match(match),
            action=body.action,
            untrusted_seed_text=body.untrusted_seed_text,
            seed_was_supplied=supplied,
        )
        response = _diagnostic_response(uow, session)
        uow.commit()
        return response
    except YunoError:
        raise
    except Exception as exc:  # noqa: BLE001 - route is the diagnostic failure boundary
        _fail_diagnostic(uow, owner_id, session_id, exc)


@router.post(
    "/diagnostics/{session_id}/answers",
    response_model=DiagnosticAnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_diagnostic_answer(
    session_id: str,
    body: DiagnosticAnswerRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsApiUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> DiagnosticAnswerResponse:
    uow.diagnostics.lock_idempotency_commands(owner_id)
    operation = f"answer_diagnostic:{session_id}"
    request_hash = hash_payload(body.model_dump(mode="json"))
    prior = uow.diagnostics.get_idempotency(owner_id, operation, key)
    if prior is not None:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different answer."
            )
        return DiagnosticAnswerResponse.model_validate_json(prior.response_json)
    try:
        answer = append_diagnostic_answer(
            uow, owner_id, session_id, **body.model_dump()
        )
        response = _answer_response(answer)
        uow.diagnostics.add_idempotency(
            DiagnosticsIdempotencyRecord(
                id=new_id(),
                owner_id=owner_id,
                operation=operation,
                idempotency_key=key,
                request_hash=request_hash,
                session_id=session_id,
                response_json=response.model_dump_json(),
                created_at=now_text(SystemClock()),
            )
        )
        uow.commit()
        return response
    except YunoError:
        raise
    except Exception as exc:  # noqa: BLE001 - route is the diagnostic failure boundary
        _fail_diagnostic(uow, owner_id, session_id, exc)


@router.get(
    "/diagnostics/{session_id}/roadmap-preview",
    response_model=DiagnosticRoadmapPreviewResponse,
)
def get_roadmap_preview(
    session_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsApiUnitOfWork, Depends(get_unit_of_work)],
) -> DiagnosticRoadmapPreviewResponse:
    session = get_diagnostic(uow, owner_id, session_id)
    if session.state is not DiagnosticState.ROADMAP_PREVIEW:
        raise ConflictError(
            "Open the roadmap preview through PATCH before reading it.",
            current_state=session.state.value,
            recovery_action="PATCH the diagnostic with action=open_roadmap_preview.",
        )
    return _diagnostic_preview_response(uow, session)


@router.put(
    "/diagnostics/{session_id}/roadmap-preview",
    response_model=DiagnosticRoadmapPreviewResponse,
)
def put_roadmap_preview(
    session_id: str,
    body: DiagnosticRoadmapPreviewUpdateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsApiUnitOfWork, Depends(get_unit_of_work)],
) -> DiagnosticRoadmapPreviewResponse:
    session = get_diagnostic(uow, owner_id, session_id)
    topics = uow.canonical.get_published_topics(session.captured_graph_version_id)
    updated = replace_roadmap_preview_edits(
        uow,
        owner_id,
        session_id,
        edits=[edit.model_dump(mode="python") for edit in body.edits],
        published_topic_ids=frozenset(topic.stable_id for topic in topics),
    )
    response = _diagnostic_preview_response(uow, updated)
    uow.commit()
    return response


@router.post(
    "/diagnostics/{session_id}/confirm-goal",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_confirm_goal(
    session_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsApiUnitOfWork, Depends(get_unit_of_work)],
) -> GoalResponse:
    """Atomically turn a persisted preview into a complete goal workspace."""
    uow.diagnostics.lock_idempotency_commands(owner_id)
    session = get_diagnostic(uow, owner_id, session_id)
    if (
        session.confirmed_goal_id is not None
        or session.state is DiagnosticState.CONFIRMED
    ):
        raise ConflictError(
            "This diagnostic has already been confirmed.",
            current_state=DiagnosticState.CONFIRMED.value,
        )
    if session.state is not DiagnosticState.ROADMAP_PREVIEW:
        raise ConflictError(
            "Open the roadmap preview before confirming the goal.",
            current_state=session.state.value,
        )
    graph = uow.canonical.get_published_version(session.captured_graph_version_id)
    topics = uow.canonical.get_published_topics(session.captured_graph_version_id)
    if graph is None:
        raise ConflictError(
            "The graph captured by this diagnostic is no longer approved.",
            current_state=session.state.value,
        )
    setup = session.setup_inputs
    try:
        path = GoalPath(str(setup["path"]))
        target_level = TargetLevel(str(setup["target_level"]))
        target_capability = TargetCapability(str(setup["target_capability"]))
    except (KeyError, ValueError) as exc:
        raise ConflictError(
            "The persisted diagnostic setup is incomplete.",
            current_state=session.state.value,
        ) from exc
    goal_name = str(setup.get("goal_name", "")).strip()
    if not goal_name:
        raise ConflictError(
            "The persisted diagnostic setup has no goal name.",
            current_state=session.state.value,
        )
    try:
        timestamp = now_text(SystemClock())
        # Re-run the pure projector at the confirmation boundary. This
        # rejects a stale/invalid ordering set before any goal row is made.
        _diagnostic_preview_response(uow, session)
        goal = create_goal(
            uow,
            owner_id,
            name=goal_name,
            path=path,
            subject=str(setup["subject"]) if setup.get("subject") is not None else None,
            role=str(setup["role"]) if setup.get("role") is not None else None,
            target_level=target_level,
            target_capability=target_capability,
            graph_version_id=session.captured_graph_version_id,
            approved_graph_exists=True,
        )
        answers = tuple(uow.diagnostics.list_answers(owner_id, session_id))
        classification = _initial_classification(session, answers)
        for topic in topics:
            state_input = {
                "session_id": session.id,
                "answers": [
                    {
                        "question_ref": answer.question_ref,
                        "answer": answer.answer,
                        "confidence": answer.confidence.value,
                    }
                    for answer in answers
                ],
                "topic_stable_id": topic.stable_id,
                "graph_version_id": session.captured_graph_version_id,
            }
            uow.roadmap.add_learning_state(
                LearningState(
                    id=new_id(),
                    owner_id=owner_id,
                    goal_id=goal.id,
                    topic_stable_id=topic.stable_id,
                    graph_version_id=session.captured_graph_version_id,
                    classification=classification,
                    origin="diagnostic" if answers else "diagnostic-skip",
                    recommended_depth=topic.recommended_layer,
                    explanation=(
                        "Initial conservative classification from saved diagnostic answers."
                        if answers
                        else "No diagnostic evidence was supplied; verify this topic explicitly."
                    ),
                    derivation_version="diagnostic-confirmation-v1",
                    input_hash=hash_payload(state_input),
                    derived_at=timestamp,
                )
            )
        preview_edits = uow.diagnostics.list_preview_edits(owner_id, session_id)
        overlay_edits = tuple(
            edit for edit in preview_edits if edit.entry_type != "correction"
        )
        if overlay_edits:
            overlay = uow.roadmap.get_or_create_overlay(
                owner_id, goal.id, session.captured_graph_version_id
            )
            for edit in overlay_edits:
                content = {
                    "graph_version_id": session.captured_graph_version_id,
                    "topic_stable_id": edit.topic_stable_id,
                    "entry_type": edit.entry_type,
                    "value": dict(edit.value),
                }
                uow.roadmap.append_overlay_entry(
                    OverlayEntry(
                        id=new_id(),
                        owner_id=owner_id,
                        goal_id=goal.id,
                        overlay_id=overlay.id,
                        graph_version_id=session.captured_graph_version_id,
                        topic_stable_id=edit.topic_stable_id,
                        entry_type=OverlayEntryType(edit.entry_type),
                        value=dict(edit.value),
                        reason=edit.reason,
                        source="diagnostic_confirmation",
                        approved_at=timestamp,
                        content_hash=hash_payload(content),
                    )
                )
        for edit in preview_edits:
            if edit.entry_type != "correction" or edit.topic_stable_id is None:
                continue
            uow.roadmap.append_correction(
                LearnerCorrection(
                    id=new_id(),
                    owner_id=owner_id,
                    goal_id=goal.id,
                    topic_stable_id=edit.topic_stable_id,
                    correction_type=CorrectionType.CORRECTION,
                    value=str(edit.value["classification"]),
                    reason=edit.reason,
                    created_at=timestamp,
                )
            )
        confirmed = uow.diagnostics.update_session(
            owner_id,
            session_id,
            session.row_version,
            {
                "state": DiagnosticState.CONFIRMED,
                "confirmed_goal_id": goal.id,
                "failure_code": None,
                "failure_reference": None,
                "updated_at": timestamp,
            },
        )
        if confirmed is None:
            raise ConflictError(
                "The diagnostic changed while it was being confirmed.",
                current_state=session.state.value,
            )
        uow.commit()
        return _goal_response(uow, goal)
    except YunoError:
        raise
    except Exception as exc:
        uow.rollback()
        raise UnavailableError(
            "Goal confirmation failed before any changes were committed.",
            current_state=DiagnosticState.ROADMAP_PREVIEW.value,
            recovery_action="Retry confirmation from the saved roadmap preview.",
        ) from exc


def _initial_classification(
    session: DiagnosticSession, answers: tuple[DiagnosticAnswer, ...]
) -> LearningClassification:
    if session.diagnostic_skipped or not answers:
        return LearningClassification.UNVERIFIED
    confidence = {"low": 0, "medium": 1, "high": 2}
    average = sum(confidence[item.confidence.value] for item in answers) / len(answers)
    if average >= 1.5:
        return LearningClassification.LIKELY_KNOWN
    if average >= 0.5:
        return LearningClassification.PARTIAL
    return LearningClassification.NEW


def _diagnostic_preview_response(
    uow: DiagnosticsApiUnitOfWork, session: DiagnosticSession
) -> DiagnosticRoadmapPreviewResponse:
    topics = tuple(
        uow.canonical.get_published_topics(session.captured_graph_version_id)
    )
    relations = uow.canonical.get_published_relations(session.captured_graph_version_id)
    answers = tuple(uow.diagnostics.list_answers(session.owner_id, session.id))
    timestamp = session.updated_at
    classification = _initial_classification(session, answers)
    learning_states = tuple(
        LearningState(
            id=f"preview-state:{topic.stable_id}",
            owner_id=session.owner_id,
            goal_id=session.id,
            topic_stable_id=topic.stable_id,
            graph_version_id=session.captured_graph_version_id,
            classification=classification,
            origin="diagnostic-preview",
            recommended_depth=topic.recommended_layer,
            explanation=(
                "Preview classification from saved diagnostic answers."
                if answers
                else "No diagnostic evidence was supplied; verify this topic explicitly."
            ),
            derivation_version="diagnostic-preview-v1",
            input_hash=hash_payload(
                {"session_id": session.id, "topic_stable_id": topic.stable_id}
            ),
            derived_at=timestamp,
        )
        for topic in topics
    )
    preview_edits = tuple(
        uow.diagnostics.list_preview_edits(session.owner_id, session.id)
    )
    overlay_entries = tuple(
        OverlayEntry(
            id=edit.id,
            owner_id=edit.owner_id,
            goal_id=session.id,
            overlay_id=session.id,
            graph_version_id=session.captured_graph_version_id,
            topic_stable_id=edit.topic_stable_id,
            entry_type=OverlayEntryType(edit.entry_type),
            value=dict(edit.value),
            reason=edit.reason,
            source="learner",
            approved_at=edit.updated_at,
            content_hash=hash_payload(edit.value),
        )
        for edit in preview_edits
        if edit.entry_type != "correction"
    )
    corrections = tuple(
        LearnerCorrection(
            id=edit.id,
            owner_id=edit.owner_id,
            goal_id=session.id,
            topic_stable_id=edit.topic_stable_id,
            correction_type=CorrectionType.CORRECTION,
            value=str(edit.value["classification"]),
            reason=edit.reason,
            created_at=edit.updated_at,
        )
        for edit in preview_edits
        if edit.entry_type == "correction" and edit.topic_stable_id is not None
    )
    projection = project_roadmap(
        graph_version_id=session.captured_graph_version_id,
        topics=(
            RoadmapTopic(
                topic.stable_id,
                topic.title,
                topic.subject,
                topic.scope_tags,
                topic.level_tag,
                topic.target_capability,
                topic.recommended_layer,
            )
            for topic in topics
        ),
        prerequisite_relations=(
            RoadmapRelation(relation.from_stable_id, relation.to_stable_id)
            for relation in relations
            if relation.relation_type is RelationType.PREREQUISITE
        ),
        overlay_entries=overlay_entries,
        learning_states=learning_states,
        corrections=corrections,
    )
    return DiagnosticRoadmapPreviewResponse(
        session_id=session.id,
        captured_graph_version_id=session.captured_graph_version_id,
        state=session.state,
        answer_count=len(answers),
        diagnostic_skipped=session.diagnostic_skipped,
        projection_version=projection.projection_version,
        topic_recommendations=[
            {
                **item.__dict__,
                "scope_tags": list(item.scope_tags),
                "classification": item.classification.value,
                "pending_proposals": list(item.pending_proposals),
                "conflicts": list(item.conflicts),
            }
            for item in projection.topics
        ],
        saved_edits=[
            {
                "topic_stable_id": edit.topic_stable_id,
                "entry_type": edit.entry_type,
                "value": dict(edit.value),
                "reason": edit.reason,
            }
            for edit in uow.diagnostics.list_preview_edits(session.owner_id, session.id)
        ],
    )


def _goal_response(uow: DiagnosticsApiUnitOfWork, goal) -> GoalResponse:
    dismissals = uow.profiles_goals.list_dismissals(goal.owner_id, goal.id)
    navigation = uow.profiles_goals.list_navigation(goal.owner_id, goal.id)
    return GoalResponse(
        id=goal.id,
        name=goal.name,
        path=goal.path,
        subject=goal.subject,
        role=goal.role,
        target_level=goal.target_level,
        target_capability=goal.target_capability,
        graph_version_id=goal.graph_version_id,
        status=goal.status,
        resume_position=goal.resume_position,
        resume_destination=navigation[-1].destination if navigation else None,
        last_accessed_at=goal.last_accessed_at,
        dismissed_recommendation_keys=[item.recommendation_key for item in dismissals],
        row_version=goal.row_version,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def _diagnostic_response(
    uow: DiagnosticsUnitOfWork, session: DiagnosticSession
) -> DiagnosticResponse:
    answers = tuple(uow.diagnostics.list_answers(session.owner_id, session.id))
    question = next_question(session, answers)
    return DiagnosticResponse(
        id=session.id,
        captured_graph_version_id=session.captured_graph_version_id,
        question_set_version=session.question_set_version,
        setup_inputs=dict(session.setup_inputs),
        state=session.state,
        untrusted_seed_kind=session.untrusted_seed_kind,
        untrusted_seed_text=session.untrusted_seed_text,
        seed_skipped=session.seed_skipped,
        diagnostic_skipped=session.diagnostic_skipped,
        answers=[_answer_response(item) for item in answers],
        next_question=(
            DiagnosticQuestionResponse(
                ref=question.ref,
                prompt=question.prompt,
                sequence=question.sequence,
                adaptive_context_version=question.adaptive_context_version,
            )
            if question is not None
            else None
        ),
        started_at=session.started_at,
        paused_at=session.paused_at,
        expires_at=session.expires_at,
        failure_code=session.failure_code,
        failure_reference=session.failure_reference,
        confirmed_goal_id=session.confirmed_goal_id,
        row_version=session.row_version,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _answer_response(answer: DiagnosticAnswer) -> DiagnosticAnswerResponse:
    return DiagnosticAnswerResponse(
        id=answer.id,
        sequence=answer.sequence,
        question_ref=answer.question_ref,
        answer=answer.answer,
        confidence=answer.confidence,
        adaptive_context_version=answer.adaptive_context_version,
        answered_at=answer.answered_at,
    )


def _fail_diagnostic(
    uow: DiagnosticsUnitOfWork,
    owner_id: str,
    session_id: str,
    cause: Exception,
) -> None:
    uow.rollback()
    record_diagnostic_failure(
        uow,
        owner_id,
        session_id,
        failure_code="diagnostic_service_failure",
        failure_reference=new_id(),
    )
    uow.commit()
    raise UnavailableError(
        "The diagnostic failed after preserving its previously saved answers.",
        current_state=DiagnosticState.FAILED.value,
        recovery_action="Retry or skip the diagnostic from the saved session.",
    ) from cause

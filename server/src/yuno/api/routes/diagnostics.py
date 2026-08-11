"""Persisted diagnostic/setup HTTP API (IDK-105)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from yuno.api.contracts import (
    DiagnosticAnswerRequest,
    DiagnosticAnswerResponse,
    DiagnosticCreateRequest,
    DiagnosticPatchRequest,
    DiagnosticQuestionResponse,
    DiagnosticResponse,
    DiagnosticRoadmapPreviewResponse,
)
from yuno.api.dependencies import (
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
    if_match,
    parse_if_match,
)
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
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    IdempotencyConflictError,
    UnavailableError,
    YunoError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["diagnostics"])


@router.post(
    "/diagnostics",
    response_model=DiagnosticResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_diagnostic(
    body: DiagnosticCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsUnitOfWork, Depends(get_unit_of_work)],
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
    uow: Annotated[DiagnosticsUnitOfWork, Depends(get_unit_of_work)],
) -> DiagnosticResponse:
    return _diagnostic_response(uow, get_diagnostic(uow, owner_id, session_id))


@router.patch("/diagnostics/{session_id}", response_model=DiagnosticResponse)
def update_diagnostic_session(
    session_id: str,
    body: DiagnosticPatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[DiagnosticsUnitOfWork, Depends(get_unit_of_work)],
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
    uow: Annotated[DiagnosticsUnitOfWork, Depends(get_unit_of_work)],
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
    uow: Annotated[DiagnosticsUnitOfWork, Depends(get_unit_of_work)],
) -> DiagnosticRoadmapPreviewResponse:
    session = get_diagnostic(uow, owner_id, session_id)
    if session.state is not DiagnosticState.ROADMAP_PREVIEW:
        raise ConflictError(
            "Open the roadmap preview through PATCH before reading it.",
            current_state=session.state.value,
            recovery_action="PATCH the diagnostic with action=open_roadmap_preview.",
        )
    answers = uow.diagnostics.list_answers(owner_id, session_id)
    return DiagnosticRoadmapPreviewResponse(
        session_id=session.id,
        captured_graph_version_id=session.captured_graph_version_id,
        state=session.state,
        answer_count=len(answers),
        diagnostic_skipped=session.diagnostic_skipped,
        projection_version="diagnostic-preview-placeholder-v1",
        topic_recommendations=[],
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

"""Interview preparation bundle and read-model API."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from yuno.api.assessment_presenter import assessment_response
from yuno.api.contracts import (
    InterviewBundleCopyRequest,
    InterviewBundleCreateRequest,
    InterviewBundlePatchRequest,
    InterviewBundleResponse,
    InterviewQuestionResponse,
    JobRefResponse,
    MockDraftRequest,
    MockReportResponse,
    MockRunResponse,
    PracticeAnswerRequest,
    PracticeRunCreateRequest,
    PracticeRunResponse,
    RefresherResponse,
    accepted_job,
)
from yuno.api.dependencies import (
    get_clock,
    get_job_dispatcher,
    get_owner_id,
    get_settings_dependency,
    get_unit_of_work,
    idempotency_key,
    if_match,
    parse_if_match,
)
from yuno.config import Settings
from yuno.modules.data_lifecycle.service import delete_interview_bodies
from yuno.modules.evidence_evaluation.domain import EvaluationRequest, RubricStatus
from yuno.modules.evidence_evaluation.ports import EvaluationAdapter
from yuno.modules.evidence_evaluation.service import create_evidence, perform_assessment
from yuno.modules.interview.domain import (
    InterviewBundle,
    InterviewIdempotencyRecord,
    PracticeDimensionResult,
    PracticeRun,
)
from yuno.modules.interview.ports import InterviewUnitOfWork, MockInterviewAdapter
from yuno.modules.interview.service import (
    append_mock_next_question,
    begin_evaluation,
    cancel_evaluation,
    cancel_mock_generation,
    complete_evaluation,
    complete_mock_evaluation,
    copy_bundle,
    create_bundle,
    create_mock_run,
    create_practice_run,
    fail_evaluation,
    fail_mock_generation,
    get_bundle,
    get_interview_run,
    get_practice_run,
    get_terminal_mock_report,
    pause_mock,
    request_hint,
    require_goal,
    reserve_evaluation_retry,
    reserve_mock_completion,
    reserve_mock_retry,
    resume_mock,
    submit_answer,
    submit_mock_answer,
    update_bundle,
    validate_mock_completion,
)
from yuno.modules.learning_content.domain import TopicLayer
from yuno.modules.learning_content.service import resolve_generation_context
from yuno.modules.provider.service import require_disclosure
from yuno.shared.application.jobs import (
    JobDispatcher,
    JobLane,
    JobRef,
    JobRequest,
    JobStatus,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import Clock, now_text
from yuno.shared.domain.errors import (
    DomainValidationError,
    IdempotencyConflictError,
    MockFeedbackWithheldError,
    NotFoundError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["interview"])


@router.post(
    "/interview-runs",
    response_model=PracticeRunResponse | MockRunResponse,
    status_code=201,
)
def post_interview_run(
    body: PracticeRunCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
):
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    if body.mode == "Mock":
        rubric_id = body.rubric_id
        rubric_version = body.rubric_version
        if (rubric_id is None) != (rubric_version is None):
            raise DomainValidationError(
                "Mock rubric ID and version must be provided together."
            )
        if rubric_id is not None:
            rubric = uow.evidence.get_rubric(owner_id, rubric_id)
            if (
                rubric is None
                or rubric.version != rubric_version
                or rubric.status is RubricStatus.RETIRED
            ):
                raise NotFoundError("The requested Mock rubric was not found.")
            if rubric.capability != body.requested_capability:
                raise DomainValidationError(
                    "The Mock capability must match its rubric."
                )
        run = create_mock_run(
            uow,
            owner_id,
            body.goal_id,
            body.bundle_id,
            body.bundle_item_id,
            rubric_id,
            rubric_version,
            body.requested_capability,
            session_owner_limit=settings.interview_sessions_owner_limit,
            turns_per_session_limit=settings.interview_turns_per_session_limit,
            bytes_per_session_limit=settings.interview_bytes_per_session_limit,
            clock=clock,
        )
        uow.commit()
        return _mock_run_response(run)
    if body.rubric_id is None or body.rubric_version is None:
        raise DomainValidationError("Practice rubric references are required.")
    rubric = uow.evidence.get_rubric(owner_id, body.rubric_id)
    if (
        rubric is None
        or rubric.version != body.rubric_version
        or rubric.status is RubricStatus.RETIRED
    ):
        raise NotFoundError("The requested Practice rubric was not found.")
    if rubric.capability != body.requested_capability:
        raise DomainValidationError("The Practice capability must match its rubric.")
    run = create_practice_run(
        uow,
        owner_id,
        body.goal_id,
        body.bundle_id,
        body.bundle_item_id,
        body.rubric_id,
        body.rubric_version,
        body.requested_capability,
        hint_text=body.hint,
        session_owner_limit=settings.interview_sessions_owner_limit,
        turns_per_session_limit=settings.interview_turns_per_session_limit,
        bytes_per_session_limit=settings.interview_bytes_per_session_limit,
        clock=clock,
    )
    uow.commit()
    return _run_response(run)


@router.get(
    "/interview-runs/{run_id}",
    response_model=PracticeRunResponse | MockRunResponse,
)
def read_interview_run(
    run_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
):
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    run = get_interview_run(uow, owner_id, run_id)
    return _run_response(run) if run.mode == "Practice" else _mock_run_response(run)


@router.delete("/interview-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview_run(
    run_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
) -> Response:
    get_interview_run(uow, owner_id, run_id)
    delete_interview_bodies(uow, owner_id, run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/interview-runs/{run_id}/hints", response_model=PracticeRunResponse)
def post_interview_hint(
    run_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
):
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    run = get_interview_run(uow, owner_id, run_id)
    if run.mode == "Mock" and run.state.value != "completed":
        raise MockFeedbackWithheldError(
            "Hints are withheld until the Mock interview is complete."
        )
    run = request_hint(
        uow,
        owner_id,
        run_id,
        turns_per_session_limit=settings.interview_turns_per_session_limit,
        bytes_per_session_limit=settings.interview_bytes_per_session_limit,
        clock=clock,
    )
    uow.commit()
    return _run_response(run)


@router.post(
    "/interview-runs/{run_id}/answers",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={202: {"model": JobRefResponse}},
)
def post_interview_answer(
    run_id: str,
    body: PracticeAnswerRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
):
    run = get_interview_run(uow, owner_id, run_id)
    if not body.answer.strip():
        raise DomainValidationError("An answer must not be blank.")
    if run.mode == "Mock":
        return _post_mock_answer(
            run, body, owner_id, uow, dispatcher, key, clock, settings
        )
    operation = f"practice_answer:{run_id}"
    request_data = body.model_dump(mode="json")
    prior = uow.interview.get_idempotency(owner_id, operation, key)
    if prior is not None:
        if prior.request_hash != hash_payload(request_data):
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different Practice answer."
            )
        reserved = JobRefResponse.model_validate_json(prior.response_json)
        current = dispatcher.get(owner_id, reserved.job_id)
        if current is not None:
            return accepted_job(current)
        run = get_practice_run(uow, owner_id, run_id)
        if run.state.value == "feedback-ready":
            return accepted_job(
                JobRef(
                    reserved.job_id,
                    reserved.kind,
                    JobStatus.SUCCEEDED,
                    reserved.enqueued_at,
                    deduplicated=True,
                )
            )
        if run.state.value == "failed-recoverable":
            return accepted_job(
                JobRef(
                    reserved.job_id,
                    reserved.kind,
                    JobStatus.FAILED,
                    reserved.enqueued_at,
                    deduplicated=True,
                )
            )
        disclosure = require_disclosure(uow, owner_id)
        return accepted_job(
            _dispatch_practice(
                dispatcher,
                owner_id,
                run,
                key,
                reserved.job_id,
                disclosure.id,
                settings,
            )
        )

    run = get_practice_run(uow, owner_id, run_id)
    bundle = get_bundle(uow, owner_id, run.bundle_id)
    item = next(value for value in bundle.items if value.id == run.bundle_item_id)
    assert item.topic_stable_id is not None
    disclosure = require_disclosure(uow, owner_id)
    job_id = new_id()
    evidence = create_evidence(
        uow,
        owner_id,
        run.goal_id,
        topic_stable_id=item.topic_stable_id,
        evidence_type="practice-answer",
        capability=run.requested_capability,
        summary=run.question,
        origin="practice-submit",
        content=body.answer,
        content_version=run.rubric_version,
        max_payload_bytes=settings.evidence_payload_max_bytes,
        retained_owner_limit=settings.evidence_retained_owner_limit,
    )
    answer_turn = submit_answer(
        uow,
        owner_id,
        run.id,
        body.answer,
        evidence.id,
        job_id,
        turns_per_session_limit=settings.interview_turns_per_session_limit,
        bytes_per_session_limit=settings.interview_bytes_per_session_limit,
        clock=clock,
    )
    reserved = JobRefResponse(
        job_id=job_id,
        kind="evaluate_practice_answer",
        status=JobStatus.QUEUED,
        enqueued_at=now_text(clock),
        deduplicated=False,
    )
    uow.interview.add_idempotency(
        InterviewIdempotencyRecord(
            new_id(),
            owner_id,
            operation,
            key,
            hash_payload(request_data),
            reserved.model_dump_json(),
            now_text(clock),
        )
    )
    # Approval boundary: the immutable answer and evidence candidate are durable
    # before dispatch can invoke an external evaluator.
    uow.commit()
    run = get_practice_run(uow, owner_id, run.id)
    assert run.active_answer_turn_id == answer_turn.id
    return accepted_job(
        _dispatch_practice(
            dispatcher, owner_id, run, key, job_id, disclosure.id, settings
        )
    )


@router.post("/interview-runs/{run_id}/pause", response_model=MockRunResponse)
def post_mock_pause(
    run_id: str,
    body: MockDraftRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
):
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    run = pause_mock(
        uow,
        owner_id,
        run_id,
        body.draft,
        bytes_per_session_limit=settings.interview_bytes_per_session_limit,
        clock=clock,
    )
    uow.commit()
    return _mock_run_response(run)


@router.post("/interview-runs/{run_id}/resume", response_model=MockRunResponse)
def post_mock_resume(
    run_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
):
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    run = resume_mock(uow, owner_id, run_id, clock=clock)
    uow.commit()
    return _mock_run_response(run)


@router.post(
    "/interview-runs/{run_id}/complete",
    response_model=JobRefResponse | MockRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={200: {"model": MockRunResponse}, 202: {"model": JobRefResponse}},
)
def post_mock_complete(
    run_id: str,
    body: MockDraftRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
):
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    run = get_interview_run(uow, owner_id, run_id)
    if run.mode != "Mock":
        raise NotFoundError("Mock run not found.")
    if run.state.value == "completed":
        return Response(
            content=_mock_run_response(run).model_dump_json(),
            media_type="application/json",
            status_code=200,
        )
    operation = f"mock_complete:{run_id}"
    request_data = body.model_dump(mode="json")
    prior = uow.interview.get_idempotency(owner_id, operation, key)
    if prior is not None:
        if prior.request_hash != hash_payload(request_data):
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different Mock draft."
            )
        reserved = JobRefResponse.model_validate_json(prior.response_json)
        current = dispatcher.get(owner_id, reserved.job_id)
        return accepted_job(current or reserved)
    if run.state.value == "completing":
        assert run.active_job_id is not None
        current = dispatcher.get(owner_id, run.active_job_id)
        ref = current or JobRef(
            run.active_job_id,
            "evaluate_mock_final",
            JobStatus.QUEUED,
            run.updated_at,
            deduplicated=True,
        )
        return accepted_job(ref)
    validate_mock_completion(
        uow,
        owner_id,
        run_id,
        body.draft,
        turns_per_session_limit=settings.interview_turns_per_session_limit,
        bytes_per_session_limit=settings.interview_bytes_per_session_limit,
    )
    bundle = get_bundle(uow, owner_id, run.bundle_id)
    item = next(value for value in bundle.items if value.id == run.bundle_item_id)
    if item.topic_stable_id is None:
        raise DomainValidationError(
            "A Mock assessment must reference an approved topic."
        )
    disclosure = require_disclosure(uow, owner_id)
    job_id = new_id()
    transcript = [
        {"kind": turn.kind.value, "body": turn.body} for turn in run.turns
    ] + [{"kind": "answer", "body": body.draft}]
    evidence = create_evidence(
        uow,
        owner_id,
        run.goal_id,
        topic_stable_id=item.topic_stable_id,
        evidence_type="mock-transcript",
        capability=run.requested_capability,
        summary="Completed Mock interview transcript",
        origin="mock-complete",
        content=json.dumps(transcript, ensure_ascii=False, separators=(",", ":")),
        content_version="mock-transcript-v1",
        max_payload_bytes=settings.evidence_payload_max_bytes,
        retained_owner_limit=settings.evidence_retained_owner_limit,
        clock=clock,
    )
    run = reserve_mock_completion(
        uow, owner_id, run_id, body.draft, job_id, evidence.id, clock=clock
    )
    reserved = JobRefResponse(
        job_id=job_id,
        kind="evaluate_mock_final",
        status=JobStatus.QUEUED,
        enqueued_at=now_text(clock),
        deduplicated=False,
    )
    uow.interview.add_idempotency(
        InterviewIdempotencyRecord(
            new_id(),
            owner_id,
            operation,
            key,
            hash_payload(request_data),
            reserved.model_dump_json(),
            now_text(clock),
        )
    )
    uow.commit()
    return accepted_job(
        dispatcher.enqueue(
            JobRequest(
                "evaluate_mock_final",
                owner_id,
                {"run_id": run.id},
                dedupe_key=run.id,
                idempotency_key=key,
                requested_job_id=job_id,
                goal_id=run.goal_id,
                lane=JobLane.INTERACTIVE,
                schema_version="provider-job-v1",
                request_ref=f"InterviewRun:{run.id}",
                disclosure_ref=disclosure.id,
            )
        )
    )


@router.get("/interview-runs/{run_id}/report", response_model=MockReportResponse)
def read_mock_report(
    run_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
):
    run, assessment = get_terminal_mock_report(uow, owner_id, run_id)
    return MockReportResponse(
        run_id=run.id,
        goal_id=run.goal_id,
        state="completed",
        assessment=assessment_response(uow, owner_id, assessment),
        transcript=[
            {
                "id": item.id,
                "turn_number": item.turn_number,
                "kind": item.kind,
                "body": item.body,
                "answer_turn_id": item.answer_turn_id,
                "created_at": item.created_at,
            }
            for item in run.turns
        ],
    )


@router.post(
    "/interview-runs/{run_id}/retry-evaluation",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={202: {"model": JobRefResponse}},
)
def post_interview_retry(
    run_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
):
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    current = get_interview_run(uow, owner_id, run_id)
    if current.mode == "Mock":
        operation = f"mock_retry:{run_id}"
        request_data: dict[str, object] = {}
        prior = uow.interview.get_idempotency(owner_id, operation, key)
        if prior is not None:
            if prior.request_hash != hash_payload(request_data):
                raise IdempotencyConflictError(
                    "The Idempotency-Key was reused with a different Mock retry."
                )
            reserved = JobRefResponse.model_validate_json(prior.response_json)
            current_job = dispatcher.get(owner_id, reserved.job_id)
            return accepted_job(current_job or reserved)
        disclosure = require_disclosure(uow, owner_id)
        job_id = new_id()
        run, kind = reserve_mock_retry(uow, owner_id, run_id, job_id, clock=clock)
        reserved = JobRefResponse(
            job_id=job_id,
            kind=kind,
            status=JobStatus.QUEUED,
            enqueued_at=now_text(clock),
            deduplicated=False,
        )
        uow.interview.add_idempotency(
            InterviewIdempotencyRecord(
                new_id(),
                owner_id,
                operation,
                key,
                hash_payload(request_data),
                reserved.model_dump_json(),
                now_text(clock),
            )
        )
        uow.commit()
        payload = {
            "run_id": run.id,
            "turns_per_session_limit": settings.interview_turns_per_session_limit,
            "bytes_per_session_limit": settings.interview_bytes_per_session_limit,
        }
        if kind == "generate_mock_next_turn":
            payload["answer_turn_id"] = run.active_answer_turn_id
        return accepted_job(
            dispatcher.enqueue(
                JobRequest(
                    kind,
                    owner_id,
                    payload,
                    dedupe_key=run.active_answer_turn_id,
                    idempotency_key=key,
                    requested_job_id=job_id,
                    goal_id=run.goal_id,
                    lane=JobLane.INTERACTIVE,
                    schema_version="provider-job-v1",
                    request_ref=f"InterviewRun:{run.id}",
                    disclosure_ref=disclosure.id,
                )
            )
        )
    disclosure = require_disclosure(uow, owner_id)
    job_id = new_id()
    run = reserve_evaluation_retry(uow, owner_id, run_id, job_id, clock=clock)
    uow.commit()
    return accepted_job(
        _dispatch_practice(
            dispatcher, owner_id, run, key, job_id, disclosure.id, settings
        )
    )


@router.post(
    "/interview-runs/{run_id}/cancel-evaluation",
    response_model=PracticeRunResponse | MockRunResponse,
)
def post_interview_cancel(
    run_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
):
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    current = get_interview_run(uow, owner_id, run_id)
    run = (
        cancel_mock_generation(uow, owner_id, run_id, clock=clock)
        if current.mode == "Mock"
        else cancel_evaluation(uow, owner_id, run_id, clock=clock)
    )
    uow.commit()
    return _mock_run_response(run) if run.mode == "Mock" else _run_response(run)


@router.get("/interview-bundles", response_model=list[InterviewBundleResponse])
def list_interview_bundles(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    goal_id: str | None = None,
):
    return [_response(value) for value in uow.interview.list_bundles(owner_id, goal_id)]


@router.post(
    "/interview-bundles", response_model=InterviewBundleResponse, status_code=201
)
def post_interview_bundle(
    body: InterviewBundleCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
    clock: Annotated[Clock, Depends(get_clock)],
):
    request_data = body.model_dump(mode="json")
    prior = _prior(uow, owner_id, "create_bundle", key, request_data)
    if prior:
        return prior
    response = _response(create_bundle(uow, owner_id, body.model_dump(), clock=clock))
    _store(uow, owner_id, "create_bundle", key, request_data, response, clock)
    uow.commit()
    return response


@router.get("/interview-bundles/{bundle_id}", response_model=InterviewBundleResponse)
def read_interview_bundle(
    bundle_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
):
    return _response(get_bundle(uow, owner_id, bundle_id))


@router.patch("/interview-bundles/{bundle_id}", response_model=InterviewBundleResponse)
def patch_interview_bundle(
    bundle_id: str,
    body: InterviewBundlePatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
    match: Annotated[str, Depends(if_match)],
):
    changes = {
        field: getattr(body, field).strip()
        if isinstance(getattr(body, field), str)
        else getattr(body, field)
        for field in ("name", "generic_role", "target_level")
        if field in body.model_fields_set
    }
    item_changes = {item.id: item.included for item in (body.items or [])}
    response = _response(
        update_bundle(
            uow,
            owner_id,
            bundle_id,
            parse_if_match(match),
            changes,
            item_changes,
            clock=clock,
        )
    )
    uow.commit()
    return response


@router.delete("/interview-bundles/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview_bundle(
    bundle_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
):
    if not uow.interview.delete_bundle(owner_id, bundle_id):
        raise NotFoundError("Interview bundle not found.")
    uow.commit()
    return Response(status_code=204)


@router.post(
    "/interview-bundles/{bundle_id}/copy",
    response_model=InterviewBundleResponse,
    status_code=201,
)
def copy_interview_bundle(
    bundle_id: str,
    body: InterviewBundleCopyRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
    clock: Annotated[Clock, Depends(get_clock)],
):
    operation = f"copy_bundle:{bundle_id}"
    request_data = body.model_dump(mode="json")
    prior = _prior(uow, owner_id, operation, key, request_data)
    if prior:
        return prior
    response = _response(copy_bundle(uow, owner_id, bundle_id, body.name, clock=clock))
    _store(uow, owner_id, operation, key, request_data, response, clock)
    uow.commit()
    return response


@router.get(
    "/goals/{goal_id}/questions", response_model=list[InterviewQuestionResponse]
)
def questions(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
):
    require_goal(uow, owner_id, goal_id)
    return [
        InterviewQuestionResponse(
            id=i.id,
            bundle_id=b.id,
            subject=i.subject,
            topic_stable_id=i.topic_stable_id,
            question=i.question,
            position=i.position,
            included=i.included,
        )
        for b in uow.interview.list_bundles(owner_id, goal_id)
        for i in b.items
        if i.included and i.question is not None
    ]


@router.get("/goals/{goal_id}/refreshers", response_model=list[RefresherResponse])
def refreshers(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[InterviewUnitOfWork, Depends(get_unit_of_work)],
):
    require_goal(uow, owner_id, goal_id)
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    assert goal is not None
    topics = {
        topic.stable_id: topic
        for topic in uow.canonical.get_published_topics(goal.graph_version_id)
    }
    corrections = {
        correction.id: correction
        for correction in uow.roadmap.list_corrections(owner_id, goal_id)
    }
    learning_states = {
        state.id: state for state in uow.roadmap.list_learning_states(owner_id, goal_id)
    }
    evidence = {item.id: item for item in uow.evidence.list_evidence(owner_id, goal_id)}
    latest_by_topic = {}
    for artifact in uow.learning_content.list_artifacts(
        owner_id, goal_id, TopicLayer.INTERVIEW.value
    ):
        latest_by_topic.setdefault(artifact.topic_stable_id, artifact)

    responses = []
    for topic_id, artifact in sorted(latest_by_topic.items()):
        snapshot = (
            uow.provenance.get_artifact_snapshot(owner_id, artifact.current_snapshot_id)
            if artifact.current_snapshot_id
            else None
        )
        refs = (
            uow.provenance.list_artifact_refs(owner_id, snapshot.id)
            if snapshot is not None
            else ()
        )
        source_ref = next(
            (ref.reference_id for ref in refs if ref.ref_kind == "source"), None
        )
        gap_ref = next(
            (
                ref.reference_id
                for ref in refs
                if ref.ref_kind in {"evidence-gap", "evidence", "learning-state"}
            ),
            None,
        )
        source = uow.provenance.get_source(owner_id, source_ref) if source_ref else None
        gap = (
            corrections.get(gap_ref)
            or learning_states.get(gap_ref)
            or evidence.get(gap_ref)
        )
        gap_text = (
            getattr(gap, "reason", None)
            or getattr(gap, "explanation", None)
            or getattr(gap, "summary", None)
        )
        linked = source is not None and gap is not None and bool(gap_text)
        if not linked:
            state = "unavailable"
        else:
            _, _, _, current_evidence_hash = resolve_generation_context(
                uow, owner_id, goal_id, topic_id, TopicLayer.INTERVIEW
            )
            state = (
                "stale"
                if snapshot is not None
                and snapshot.evidence_state_hash != current_evidence_hash
                else "ready"
            )
        topic = topics.get(topic_id)
        responses.append(
            RefresherResponse(
                artifact_id=artifact.id,
                state=state,
                subject=topic.subject if topic is not None else topic_id,
                layer=artifact.layer.value,
                content=artifact.body,
                source_ref=source_ref if source is not None else None,
                source_title=source.title if source is not None else None,
                evidence_gap_ref=gap_ref if gap is not None else None,
                evidence_gap=gap_text,
            )
        )
    return responses


def _dispatch_practice(
    dispatcher: JobDispatcher,
    owner_id: str,
    run: PracticeRun,
    key: str,
    job_id: str,
    disclosure_ref: str,
    settings: Settings,
):
    assert run.active_answer_turn_id is not None
    return dispatcher.enqueue(
        JobRequest(
            "evaluate_practice_answer",
            owner_id,
            {
                "run_id": run.id,
                "answer_turn_id": run.active_answer_turn_id,
                "turns_per_session_limit": (settings.interview_turns_per_session_limit),
                "bytes_per_session_limit": (settings.interview_bytes_per_session_limit),
            },
            dedupe_key=run.active_answer_turn_id,
            idempotency_key=key,
            requested_job_id=job_id,
            goal_id=run.goal_id,
            lane=JobLane.INTERACTIVE,
            schema_version="provider-job-v1",
            request_ref=f"InterviewRun:{run.id}",
            disclosure_ref=disclosure_ref,
        )
    )


def _post_mock_answer(
    run: PracticeRun,
    body: PracticeAnswerRequest,
    owner_id: str,
    uow: InterviewUnitOfWork,
    dispatcher: JobDispatcher,
    key: str,
    clock: Clock,
    settings: Settings,
):
    operation = f"mock_answer:{run.id}"
    request_data = body.model_dump(mode="json")
    prior = uow.interview.get_idempotency(owner_id, operation, key)
    if prior is not None:
        if prior.request_hash != hash_payload(request_data):
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different Mock answer."
            )
        reserved = JobRefResponse.model_validate_json(prior.response_json)
        current = dispatcher.get(owner_id, reserved.job_id)
        return accepted_job(current or reserved)
    disclosure_ref = require_disclosure(uow, owner_id).id
    job_id = new_id()
    updated = submit_mock_answer(
        uow,
        owner_id,
        run.id,
        body.answer,
        job_id,
        turns_per_session_limit=settings.interview_turns_per_session_limit,
        bytes_per_session_limit=settings.interview_bytes_per_session_limit,
        clock=clock,
    )
    reserved = JobRefResponse(
        job_id=job_id,
        kind="generate_mock_next_turn",
        status=JobStatus.QUEUED,
        enqueued_at=now_text(clock),
        deduplicated=False,
    )
    uow.interview.add_idempotency(
        InterviewIdempotencyRecord(
            new_id(),
            owner_id,
            operation,
            key,
            hash_payload(request_data),
            reserved.model_dump_json(),
            now_text(clock),
        )
    )
    uow.commit()
    return accepted_job(
        dispatcher.enqueue(
            JobRequest(
                "generate_mock_next_turn",
                owner_id,
                {
                    "run_id": updated.id,
                    "answer_turn_id": updated.active_answer_turn_id,
                    "turns_per_session_limit": (
                        settings.interview_turns_per_session_limit
                    ),
                    "bytes_per_session_limit": (
                        settings.interview_bytes_per_session_limit
                    ),
                },
                dedupe_key=updated.active_answer_turn_id,
                idempotency_key=key,
                requested_job_id=job_id,
                goal_id=updated.goal_id,
                lane=JobLane.INTERACTIVE,
                schema_version="provider-job-v1",
                request_ref=f"InterviewRun:{updated.id}",
                disclosure_ref=disclosure_ref,
            )
        )
    )


def run_mock_next_turn_job(
    request: JobRequest,
    uow_factory: UnitOfWorkFactory,
    adapter: MockInterviewAdapter,
) -> None:
    run_id = str(request.payload["run_id"])
    answer_turn_id = str(request.payload["answer_turn_id"])
    try:
        with uow_factory() as uow:
            run = get_interview_run(uow, request.owner_id, run_id)
        question = adapter.next_question(run)
        with uow_factory() as uow:
            uow.profiles_goals.lock_idempotency_commands(request.owner_id)
            append_mock_next_question(
                uow,
                request.owner_id,
                run_id,
                answer_turn_id,
                question,
                turns_per_session_limit=int(request.payload["turns_per_session_limit"]),
                bytes_per_session_limit=int(request.payload["bytes_per_session_limit"]),
            )
            uow.commit()
            return get_interview_run(uow, request.owner_id, run_id)
    except Exception as exc:
        with uow_factory() as uow:
            fail_mock_generation(
                uow,
                request.owner_id,
                run_id,
                answer_turn_id,
                f"{type(exc).__name__}:mock-next-turn",
            )
            uow.commit()
        raise


def run_mock_final_evaluation_job(
    request: JobRequest,
    uow_factory: UnitOfWorkFactory,
    adapter: EvaluationAdapter,
) -> None:
    run_id = str(request.payload["run_id"])
    try:
        with uow_factory() as uow:
            run = get_interview_run(uow, request.owner_id, run_id)
            if run.rubric_id is None or run.rubric_version is None:
                raise RuntimeError("A reviewed Mock rubric is not configured.")
            answer = next(
                turn for turn in reversed(run.turns) if turn.kind.value == "answer"
            )
            if answer.evidence_id is None:
                raise RuntimeError("The fixed Mock transcript has no evidence.")
            rubric = uow.evidence.get_rubric(request.owner_id, run.rubric_id)
            if rubric is None or rubric.version != run.rubric_version:
                raise RuntimeError("The reviewed Mock rubric is unavailable.")
            evaluation_request = EvaluationRequest(
                answer.evidence_id,
                rubric.task_context,
                rubric.id,
                rubric.version,
                (),
                run.requested_capability,
                (),
                (rubric.provenance,) if rubric.provenance.strip() else (),
                rubric.role,
                rubric.level,
                "interactive",
            )
            uow.commit()
        with uow_factory() as uow:
            uow.profiles_goals.lock_idempotency_commands(request.owner_id)
            assessment = perform_assessment(
                uow,
                adapter,
                request.owner_id,
                evaluation_request,
                run_id=run_id,
            )
            complete_mock_evaluation(uow, request.owner_id, run_id, assessment.id)
            uow.commit()
            return assessment
    except Exception as exc:
        with uow_factory() as uow:
            run = get_interview_run(uow, request.owner_id, run_id)
            if run.active_answer_turn_id is not None:
                fail_mock_generation(
                    uow,
                    request.owner_id,
                    run_id,
                    run.active_answer_turn_id,
                    f"{type(exc).__name__}:mock-final-evaluation",
                )
                uow.commit()
        raise


def run_practice_evaluation_job(
    request: JobRequest,
    uow_factory: UnitOfWorkFactory,
    adapter: EvaluationAdapter,
) -> None:
    run_id = str(request.payload["run_id"])
    answer_turn_id = str(request.payload["answer_turn_id"])
    try:
        with uow_factory() as uow:
            run = begin_evaluation(uow, request.owner_id, run_id, answer_turn_id)
            answer = next(turn for turn in run.turns if turn.id == answer_turn_id)
            if answer.evidence_id is None:
                raise RuntimeError("The Practice attempt has no evidence candidate.")
            rubric = uow.evidence.get_rubric(request.owner_id, run.rubric_id)
            if rubric is None:
                raise RuntimeError("The Practice rubric is unavailable.")
            evaluation_request = EvaluationRequest(
                answer.evidence_id,
                rubric.task_context,
                rubric.id,
                rubric.version,
                (),
                run.requested_capability,
                (),
                (rubric.provenance,) if rubric.provenance.strip() else (),
                rubric.role,
                rubric.level,
                "interactive",
            )
            uow.commit()

        with uow_factory() as uow:
            assessment = perform_assessment(
                uow, adapter, request.owner_id, evaluation_request, run_id=run_id
            )
            rubric_dimensions = {
                item.id: item
                for item in uow.evidence.list_rubric_dimensions(
                    request.owner_id, assessment.rubric_id
                )
            }
            dimensions = tuple(
                PracticeDimensionResult(
                    rubric_dimensions[item.rubric_dimension_id].stable_dimension_id,
                    rubric_dimensions[item.rubric_dimension_id].name,
                    item.outcome.value,
                    item.rationale,
                )
                for item in uow.evidence.list_assessment_dimensions(
                    request.owner_id, assessment.id
                )
            )
            complete_evaluation(
                uow,
                request.owner_id,
                run_id,
                answer_turn_id,
                assessment.id,
                facts=assessment.facts,
                trade_offs=assessment.trade_offs,
                dimensions=dimensions,
                feedback=assessment.feedback,
                cross_question_candidate=assessment.cross_question_candidate,
                turns_per_session_limit=int(request.payload["turns_per_session_limit"]),
                bytes_per_session_limit=int(request.payload["bytes_per_session_limit"]),
            )
            uow.commit()
            return assessment
    except Exception as exc:
        with uow_factory() as uow:
            fail_evaluation(
                uow,
                request.owner_id,
                run_id,
                answer_turn_id,
                f"{type(exc).__name__}:practice-evaluation",
            )
            uow.commit()
        raise


def _run_response(run: PracticeRun) -> PracticeRunResponse:
    terminal_results = run.results if run.state.value == "feedback-ready" else ()
    return PracticeRunResponse(
        id=run.id,
        goal_id=run.goal_id,
        bundle_id=run.bundle_id,
        bundle_item_id=run.bundle_item_id,
        mode="Practice",
        state=run.state,
        question=run.question,
        rubric_id=run.rubric_id,
        rubric_version=run.rubric_version,
        requested_capability=run.requested_capability,
        active_job_id=run.active_job_id,
        failure_reference=run.failure_reference,
        retryable=run.retryable,
        created_at=run.created_at,
        updated_at=run.updated_at,
        turns=[
            {
                "id": item.id,
                "turn_number": item.turn_number,
                "kind": item.kind,
                "body": item.body,
                "answer_turn_id": item.answer_turn_id,
                "created_at": item.created_at,
            }
            for item in run.turns
        ],
        results=[
            {
                "id": item.id,
                "answer_turn_id": item.answer_turn_id,
                "assessment_id": item.assessment_id,
                "visible_at": item.visible_at,
                "facts": list(item.facts),
                "trade_offs": list(item.trade_offs),
                "dimensions": [dimension.__dict__ for dimension in item.dimensions],
                "feedback": item.feedback,
                "cross_question_candidate": item.cross_question_candidate,
            }
            for item in terminal_results
        ],
    )


def _mock_run_response(run: PracticeRun) -> MockRunResponse:
    return MockRunResponse(
        id=run.id,
        goal_id=run.goal_id,
        bundle_id=run.bundle_id,
        bundle_item_id=run.bundle_item_id,
        mode="Mock",
        state=run.state.value,
        question=run.question,
        draft=run.draft,
        active_job_id=run.active_job_id,
        failure_reference=run.failure_reference,
        retryable=run.retryable,
        final_assessment_id=run.final_assessment_id,
        created_at=run.created_at,
        updated_at=run.updated_at,
        turns=[
            {
                "id": item.id,
                "turn_number": item.turn_number,
                "kind": item.kind,
                "body": item.body,
                "answer_turn_id": item.answer_turn_id,
                "created_at": item.created_at,
            }
            for item in run.turns
        ],
    )


def _response(bundle: InterviewBundle) -> InterviewBundleResponse:
    return InterviewBundleResponse(
        **{k: v for k, v in bundle.__dict__.items() if k not in {"owner_id", "items"}},
        items=[
            {k: v for k, v in item.__dict__.items() if k != "owner_id"}
            for item in bundle.items
        ],
    )


def _prior(uow, owner_id, operation, key, data):
    record = uow.interview.get_idempotency(owner_id, operation, key)
    if not record:
        return None
    if record.request_hash != hash_payload(data):
        raise IdempotencyConflictError(
            "The Idempotency-Key was reused with a different interview request."
        )
    return InterviewBundleResponse.model_validate_json(record.response_json)


def _store(uow, owner_id, operation, key, data, response, clock):
    uow.interview.add_idempotency(
        InterviewIdempotencyRecord(
            new_id(),
            owner_id,
            operation,
            key,
            hash_payload(data),
            response.model_dump_json(),
            now_text(clock),
        )
    )

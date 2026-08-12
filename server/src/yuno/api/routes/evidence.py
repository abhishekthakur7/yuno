"""Immutable evidence and schema-validated evaluation API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from yuno.api.assessment_presenter import assessment_response
from yuno.api.contracts import (
    AssessmentCreateRequest,
    AssessmentDisputeRequest,
    AssessmentDisputeResponse,
    AssessmentReevaluateRequest,
    AssessmentResponse,
    EvidenceCreateRequest,
    EvidenceDetailResponse,
    EvidenceResponse,
    EvidenceTransferResponse,
    GoalProgressResponse,
    JobRefResponse,
    LearningStateExplanationsResponse,
    accepted_job,
)
from yuno.api.dependencies import (
    get_clock,
    get_job_dispatcher,
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
)
from yuno.modules.evidence_evaluation.domain import (
    EvaluationRequest,
    EvidenceEvaluationIdempotencyRecord,
)
from yuno.modules.evidence_evaluation.ports import (
    EvaluationAdapter,
    EvidenceUnitOfWork,
)
from yuno.modules.evidence_evaluation.service import (
    complete_reevaluation,
    create_dispute,
    create_evidence,
    fail_reevaluation,
    get_assessment,
    get_derived_progress,
    get_evidence_record,
    list_goal_evidence,
    perform_assessment,
    request_reevaluation,
)
from yuno.shared.application.jobs import JobDispatcher, JobRef, JobRequest, JobStatus
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import IdempotencyConflictError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["evidence-evaluation"])


@router.get("/goals/{goal_id}/progress", response_model=GoalProgressResponse)
def get_goal_progress(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> GoalProgressResponse:
    result = get_derived_progress(uow, owner_id, goal_id, clock=clock)
    uow.commit()
    values = {
        name: {
            **getattr(result, name).__dict__,
            "supporting_evidence_refs": list(
                getattr(result, name).supporting_evidence_refs
            ),
        }
        for name in ("coverage", "proficiency", "retention", "readiness")
    }
    return GoalProgressResponse(
        **values,
        rule_version=result.rule_version,
        effective_now=result.effective_now,
        input_hash=result.input_hash,
    )


@router.get(
    "/goals/{goal_id}/learning-state-explanations",
    response_model=LearningStateExplanationsResponse,
)
def get_learning_state_explanations(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> LearningStateExplanationsResponse:
    result = get_derived_progress(uow, owner_id, goal_id, clock=clock)
    uow.commit()
    states = [
        {
            **item.__dict__,
            "supporting_evidence_refs": list(item.supporting_evidence_refs),
        }
        for item in result.learning_states
    ]
    return LearningStateExplanationsResponse(
        learning_states=states,
        rule_version=result.rule_version,
        effective_now=result.effective_now,
        input_hash=result.input_hash,
    )


@router.post(
    "/goals/{goal_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_evidence(
    goal_id: str,
    body: EvidenceCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> EvidenceResponse:
    request_data = body.model_dump(mode="json")
    operation = f"create_evidence:{goal_id}"
    prior = _prior(uow, owner_id, operation, key, request_data, EvidenceResponse)
    if prior is not None:
        return prior
    evidence = create_evidence(uow, owner_id, goal_id, **body.model_dump())
    response = _evidence_response(uow, owner_id, evidence)
    _store(uow, owner_id, operation, key, request_data, response)
    uow.commit()
    return response


@router.get("/goals/{goal_id}/evidence", response_model=list[EvidenceResponse])
def get_goal_evidence(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
) -> list[EvidenceResponse]:
    return [
        _evidence_response(uow, owner_id, item)
        for item in list_goal_evidence(uow, owner_id, goal_id)
    ]


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetailResponse)
def get_evidence(
    evidence_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
) -> EvidenceDetailResponse:
    evidence, payload = get_evidence_record(uow, owner_id, evidence_id)
    return EvidenceDetailResponse(
        **_evidence_response(uow, owner_id, evidence).model_dump(),
        content=payload.content if payload else None,
        content_version=payload.content_version if payload else None,
        tombstoned=payload is None,
        transfers=[
            EvidenceTransferResponse(**item.__dict__)
            for item in uow.roadmap.list_evidence_transfers(owner_id, evidence.id)
        ],
    )


@router.post(
    "/evidence/{evidence_id}/assess",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={202: {"model": JobRefResponse}},
)
def post_assess(
    evidence_id: str,
    body: AssessmentCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
):
    evidence, _ = get_evidence_record(uow, owner_id, evidence_id)
    payload = {
        "evaluation_request": {
            "evidence_id": evidence.id,
            **body.model_dump(exclude={"run_id"}),
        },
        "run_id": body.run_id,
    }
    ref = dispatcher.enqueue(
        JobRequest("assess_evidence", owner_id, payload, evidence.id, key)
    )
    return accepted_job(ref)


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
def get_assessment_record(
    assessment_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
) -> AssessmentResponse:
    return assessment_response(
        uow, owner_id, get_assessment(uow, owner_id, assessment_id)
    )


@router.post(
    "/assessments/{assessment_id}/disputes",
    response_model=AssessmentDisputeResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_dispute(
    assessment_id: str,
    body: AssessmentDisputeRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> AssessmentDisputeResponse:
    request_data = body.model_dump(mode="json")
    operation = f"dispute_assessment:{assessment_id}"
    prior = _prior(
        uow, owner_id, operation, key, request_data, AssessmentDisputeResponse
    )
    if prior is not None:
        return prior
    dispute = create_dispute(uow, owner_id, assessment_id, body.reason)
    response = AssessmentDisputeResponse(
        **{
            field: value
            for field, value in dispute.__dict__.items()
            if field not in {"owner_id", "resolved_at", "resolution_note"}
        }
    )
    _store(uow, owner_id, operation, key, request_data, response)
    uow.commit()
    return response


@router.post(
    "/assessments/{assessment_id}/reevaluate",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={202: {"model": JobRefResponse}},
)
def post_reevaluate(
    assessment_id: str,
    body: AssessmentReevaluateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[EvidenceUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
):
    request_data = body.model_dump(mode="json")
    operation = f"reevaluate_assessment:{assessment_id}"
    request_hash = hash_payload(request_data)
    prior = uow.evidence.get_idempotency(owner_id, operation, key)
    if prior is not None:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different evidence/evaluation request."
            )
        if prior.completed:
            return accepted_job(
                JobRef(
                    **JobRefResponse.model_validate_json(
                        prior.response_json
                    ).model_dump()
                )
            )
        request = (
            uow.evidence.get_reevaluation_request(owner_id, prior.request_ref)
            if prior.request_ref is not None
            else None
        )
        if request is None:
            raise RuntimeError("The re-evaluation idempotency reservation is invalid.")
    else:
        job_id = new_id()
        request = request_reevaluation(
            uow, owner_id, assessment_id, body.dispute_id, job_id=job_id
        )
        # Persist the request and job identity before dispatch so a retry can
        # redispatch it if enqueue fails.
        uow.evidence.add_idempotency(
            EvidenceEvaluationIdempotencyRecord(
                new_id(),
                owner_id,
                operation,
                key,
                request_hash,
                "{}",
                now_text(SystemClock()),
                request.id,
                False,
            )
        )
        uow.commit()

    ref = dispatcher.get(owner_id, request.job_id)
    if ref is None and request.status.value == "requested":
        ref = dispatcher.enqueue(
            JobRequest(
                "reevaluate_assessment",
                owner_id,
                {"request_id": request.id},
                request.id,
                key,
                requested_job_id=request.job_id,
            )
        )
    elif ref is None:
        ref = JobRef(
            request.job_id,
            "reevaluate_assessment",
            JobStatus.SUCCEEDED
            if request.status.value == "completed"
            else JobStatus.FAILED,
            request.requested_at,
            deduplicated=True,
        )
    response = JobRefResponse(
        job_id=ref.job_id,
        kind=ref.kind,
        status=ref.status,
        enqueued_at=ref.enqueued_at,
        deduplicated=ref.deduplicated,
    )
    uow.evidence.complete_idempotency(
        owner_id, operation, key, response.model_dump_json()
    )
    uow.commit()
    return accepted_job(ref)


def run_assessment_job(
    request: JobRequest, uow_factory: UnitOfWorkFactory, adapter: EvaluationAdapter
):
    raw = dict(request.payload["evaluation_request"])
    raw["assumptions"] = tuple(raw["assumptions"])
    raw["source_refs"] = tuple(raw["source_refs"])
    raw["provenance_refs"] = tuple(raw["provenance_refs"])
    with uow_factory() as uow:
        assessment = perform_assessment(
            uow,
            adapter,
            request.owner_id,
            EvaluationRequest(**raw),
            run_id=request.payload.get("run_id"),
        )
        uow.commit()
        return assessment


def run_reevaluation_job(
    request: JobRequest, uow_factory: UnitOfWorkFactory, adapter: EvaluationAdapter
):
    request_id = str(request.payload["request_id"])
    try:
        with uow_factory() as uow:
            assessment = complete_reevaluation(
                uow, adapter, request.owner_id, request_id
            )
            uow.commit()
            return assessment
    except Exception:
        with uow_factory() as uow:
            fail_reevaluation(
                uow, request.owner_id, request_id, f"reevaluation:{request_id}"
            )
            uow.commit()
        raise


def _evidence_response(
    uow: EvidenceUnitOfWork, owner_id: str, evidence
) -> EvidenceResponse:
    active = uow.evidence.get_active_assessment_for_evidence(owner_id, evidence.id)
    return EvidenceResponse(
        **{key: value for key, value in evidence.__dict__.items() if key != "owner_id"},
        active_assessment_id=active.id if active else None,
    )


def _prior[ResponseModel: BaseModel](
    uow: EvidenceUnitOfWork,
    owner_id: str,
    operation: str,
    key: str,
    request: dict[str, object],
    response_type: type[ResponseModel],
) -> ResponseModel | None:
    prior = uow.evidence.get_idempotency(owner_id, operation, key)
    if prior is None:
        return None
    if prior.request_hash != hash_payload(request):
        raise IdempotencyConflictError(
            "The Idempotency-Key was reused with a different evidence/evaluation request."
        )
    return response_type.model_validate_json(prior.response_json)


def _store(
    uow: EvidenceUnitOfWork,
    owner_id: str,
    operation: str,
    key: str,
    request: dict[str, object],
    response: BaseModel,
) -> None:
    uow.evidence.add_idempotency(
        EvidenceEvaluationIdempotencyRecord(
            new_id(),
            owner_id,
            operation,
            key,
            hash_payload(request),
            response.model_dump_json(),
            now_text(SystemClock()),
        )
    )

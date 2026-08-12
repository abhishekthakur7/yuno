from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from yuno.api.contracts import (
    JobAttemptResponse,
    JobListResponse,
    JobRefResponse,
    JobRetryRequest,
)
from yuno.api.dependencies import get_job_dispatcher, get_owner_id
from yuno.shared.application.jobs import JobDispatcher, JobRef

router = APIRouter(tags=["jobs"])


def _response(ref: JobRef) -> JobRefResponse:
    return JobRefResponse(
        job_id=ref.job_id,
        kind=ref.kind,
        status=ref.status,
        enqueued_at=ref.enqueued_at,
        deduplicated=ref.deduplicated,
        lane=ref.lane,
        retryable=ref.retryable,
        goal_id=ref.goal_id,
        schema_version=ref.schema_version,
        attempt=ref.attempt,
        diagnostic=ref.diagnostic,
        started_at=ref.started_at,
        terminal_at=ref.terminal_at,
        substitution_ref=ref.substitution_ref,
        result_ref=ref.result_ref,
        result_hash=ref.result_hash,
    )


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    owner_id: Annotated[str, Depends(get_owner_id)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
):
    config = getattr(
        dispatcher,
        "configuration",
        {
            "pending_job_cap": 0,
            "background_age_promotion_seconds": 0,
            "janitor_retention_seconds": 0,
        },
    )
    return JobListResponse(
        jobs=[_response(ref) for ref in dispatcher.list(owner_id)], **config
    )


@router.get("/jobs/{job_id}", response_model=JobRefResponse)
def get_job(
    job_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
):
    from yuno.shared.domain.errors import NotFoundError

    ref = dispatcher.get(owner_id, job_id)
    if ref is None:
        raise NotFoundError("The requested job was not found.")
    return _response(ref)


@router.get("/jobs/{job_id}/attempts", response_model=list[JobAttemptResponse])
def get_job_attempts(
    job_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
):
    return [
        JobAttemptResponse(**attempt.__dict__)
        for attempt in dispatcher.attempts(owner_id, job_id)
    ]


@router.post("/jobs/{job_id}/retry", response_model=JobRefResponse)
def retry_job(
    job_id: str,
    body: JobRetryRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
):
    return _response(
        dispatcher.retry(
            owner_id,
            job_id,
            substitution_ref=body.substitution_ref,
            confirmation_ref=body.confirmation_ref,
        )
    )


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def cancel_job(
    job_id: str,
    response: Response,
    owner_id: Annotated[str, Depends(get_owner_id)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
):
    ref = dispatcher.cancel(owner_id, job_id)
    if ref.status.value in ("succeeded", "failed", "cancelled"):
        response.status_code = 200
    return _response(ref)


@router.post("/jobs/{job_id}/reconcile", response_model=JobRefResponse)
def reconcile_job(
    job_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
):
    return _response(dispatcher.reconcile(owner_id, job_id))

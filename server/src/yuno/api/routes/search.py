from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from yuno.api.contracts import (
    JobRefResponse,
    SearchIndexStatusResponse,
    SearchResponse,
    SearchResultResponse,
    accepted_job,
)
from yuno.api.dependencies import (
    get_job_dispatcher,
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
)
from yuno.modules.search.domain import SearchIndexState, SearchIndexStatus
from yuno.modules.search.ports import SearchUnitOfWork
from yuno.shared.application.jobs import JobDispatcher, JobLane, JobRequest

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    q: Annotated[str, Query(min_length=1, pattern=r".*\S.*")],
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SearchUnitOfWork, Depends(get_unit_of_work)],
    types: str | None = None,
) -> SearchResponse:
    normalized_query = q.strip()
    selected_types = tuple(
        value.strip() for value in (types or "").split(",") if value.strip()
    )
    state = uow.search.state(owner_id)
    results = uow.search.search(owner_id, goal_id, normalized_query, selected_types)
    return SearchResponse(
        results=[SearchResultResponse(**item.__dict__) for item in results],
        empty=not results,
        degraded=any(result.degraded for result in results)
        or (
            not results
            and state.status in (SearchIndexStatus.STALE, SearchIndexStatus.UNAVAILABLE)
        ),
        index_status=state.status,
    )


@router.get("/search-index/status", response_model=SearchIndexStatusResponse)
def search_index_status(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SearchUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
) -> SearchIndexStatusResponse:
    state = uow.search.state(owner_id)
    if state.status is SearchIndexStatus.REBUILDING and state.rebuild_job_id:
        job = dispatcher.get(owner_id, state.rebuild_job_id)
        if job and job.status.value == "failed":
            failure_reference = f"job:{state.rebuild_job_id}:failed"
            uow.search.mark_failed(
                owner_id,
                state.rebuild_job_id,
                failure_reference,
            )
            uow.commit()
            state = SearchIndexState(
                SearchIndexStatus.FAILED,
                state.source_watermark,
                state.active_generation,
                state.rebuild_job_id,
                failure_reference,
                state.updated_at,
            )
    return SearchIndexStatusResponse(**state.__dict__)


@router.post("/search-index/rebuild", status_code=202, response_model=JobRefResponse)
def rebuild_search_index(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SearchUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
):
    ref = dispatcher.enqueue(
        JobRequest(
            kind="rebuild_index",
            owner_id=owner_id,
            payload={},
            dedupe_key="search-index",
            idempotency_key=key,
            lane=JobLane.BACKGROUND,
            schema_version="search-v1",
            request_ref="SearchIndex:default",
        )
    )
    # The conditional write cannot regress a rebuild that already completed,
    # and a deduplicated enqueue records the actual existing job id.
    uow.search.mark_rebuilding(owner_id, ref.job_id)
    current = dispatcher.get(owner_id, ref.job_id)
    if current and current.status.value == "failed":
        uow.search.mark_failed(owner_id, ref.job_id, f"job:{ref.job_id}:failed")
    uow.commit()
    return accepted_job(ref)

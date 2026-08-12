"""Goal notebook and optional review queue API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from yuno.api.contracts import (
    NotebookEntryCreateRequest,
    NotebookEntryPatchRequest,
    NotebookEntryResponse,
    ReviewAttemptCreateRequest,
    ReviewAttemptResponse,
    ReviewItemResponse,
    ReviewPreferencesPatchRequest,
    ReviewPreferencesResponse,
    ReviewQueueResponse,
)
from yuno.api.dependencies import (
    get_clock,
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
    if_match,
    parse_if_match,
)
from yuno.modules.notebook_review.domain import (
    NotebookEntry,
    NotebookReviewIdempotencyRecord,
    ReviewAttempt,
    ReviewItem,
    ReviewItemStatus,
)
from yuno.modules.notebook_review.ports import NotebookReviewUnitOfWork, ReviewScheduler
from yuno.modules.notebook_review.service import (
    create_notebook_entry,
    delete_notebook_entry,
    dismiss_review_item,
    get_notebook_entry,
    get_review_preferences,
    list_notebook_entries,
    list_reviews,
    record_review_attempt,
    update_notebook_entry,
    update_review_preferences,
)
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import IdempotencyConflictError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["notebook-review"])


@router.get("/goals/{goal_id}/notebook", response_model=list[NotebookEntryResponse])
def get_notebook(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[NotebookReviewUnitOfWork, Depends(get_unit_of_work)],
) -> list[NotebookEntryResponse]:
    return [
        _entry_response(item) for item in list_notebook_entries(uow, owner_id, goal_id)
    ]


@router.post(
    "/goals/{goal_id}/notebook",
    response_model=NotebookEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_notebook_entry(
    goal_id: str,
    body: NotebookEntryCreateRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[NotebookReviewUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> NotebookEntryResponse:
    operation = f"create_notebook_entry:{goal_id}"
    request_data = body.model_dump(mode="json")
    prior = _prior(uow, owner_id, operation, key, request_data, NotebookEntryResponse)
    if prior is not None:
        return prior
    response = _entry_response(
        create_notebook_entry(uow, owner_id, goal_id, **body.model_dump())
    )
    _store(uow, owner_id, operation, key, request_data, response)
    uow.commit()
    return response


@router.patch("/notebook/{entry_id}", response_model=NotebookEntryResponse)
def patch_notebook_entry(
    entry_id: str,
    body: NotebookEntryPatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[NotebookReviewUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
) -> NotebookEntryResponse:
    expected = parse_if_match(match)
    before = get_notebook_entry(uow, owner_id, entry_id)
    supplied = body.model_fields_set
    updated = update_notebook_entry(
        uow,
        owner_id,
        entry_id,
        expected_version=expected,
        markdown=body.markdown if "markdown" in supplied else before.markdown,
        topic_stable_id=body.topic_stable_id
        if "topic_stable_id" in supplied
        else before.topic_stable_id,
        evidence_id=body.evidence_id
        if "evidence_id" in supplied
        else before.evidence_id,
        source_id=body.source_id if "source_id" in supplied else before.source_id,
    )
    response = _entry_response(updated)
    uow.commit()
    return response


@router.delete("/notebook/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook(
    entry_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[NotebookReviewUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
    key: Annotated[str, Depends(idempotency_key)],
) -> Response:
    expected = parse_if_match(match)
    operation = f"delete_notebook_entry:{entry_id}"
    request_data = {"expected_version": expected}
    prior = uow.notebook_review.get_idempotency(owner_id, operation, key)
    if prior is not None:
        if prior.request_hash != hash_payload(request_data):
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused with a different notebook request."
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    delete_notebook_entry(uow, owner_id, entry_id, expected_version=expected)
    _store_raw(uow, owner_id, operation, key, request_data, "{}")
    uow.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/goals/{goal_id}/review-preferences", response_model=ReviewPreferencesResponse
)
def get_preferences(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[NotebookReviewUnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ReviewPreferencesResponse:
    return _preferences_response(
        get_review_preferences(uow, owner_id, goal_id, clock=clock)
    )


@router.patch(
    "/goals/{goal_id}/review-preferences", response_model=ReviewPreferencesResponse
)
def patch_preferences(
    goal_id: str,
    body: ReviewPreferencesPatchRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[NotebookReviewUnitOfWork, Depends(get_unit_of_work)],
    match: Annotated[str, Depends(if_match)],
) -> ReviewPreferencesResponse:
    expected = parse_if_match(match)
    before = get_review_preferences(uow, owner_id, goal_id)
    supplied = body.model_fields_set
    response = _preferences_response(
        update_review_preferences(
            uow,
            owner_id,
            goal_id,
            expected_version=expected,
            enabled=body.enabled if "enabled" in supplied else before.enabled,
            duration_minutes=body.duration_minutes
            if "duration_minutes" in supplied
            else before.duration_minutes,
            cadence=body.cadence if "cadence" in supplied else before.cadence,
            retrieval_enabled=body.retrieval_enabled
            if "retrieval_enabled" in supplied
            else before.retrieval_enabled,
            varied_context_enabled=body.varied_context_enabled
            if "varied_context_enabled" in supplied
            else before.varied_context_enabled,
        )
    )
    uow.commit()
    return response


@router.get("/goals/{goal_id}/reviews", response_model=ReviewQueueResponse)
def get_reviews(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[NotebookReviewUnitOfWork, Depends(get_unit_of_work)],
) -> ReviewQueueResponse:
    preferences = get_review_preferences(uow, owner_id, goal_id)
    items = list_reviews(uow, owner_id, goal_id)
    return ReviewQueueResponse(
        goal_id=goal_id,
        enabled=preferences.enabled,
        scheduling_version=preferences.scheduling_version,
        items=[
            _review_response(
                item, reveal=bool(uow.notebook_review.list_attempts(owner_id, item.id))
            )
            for item in items
        ],
    )


@router.post(
    "/reviews/{review_id}/attempts",
    response_model=ReviewAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_review_attempt(
    review_id: str,
    body: ReviewAttemptCreateRequest,
    request: Request,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[NotebookReviewUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> ReviewAttemptResponse:
    operation = f"attempt_review:{review_id}"
    request_data = body.model_dump(mode="json")
    prior = _prior(uow, owner_id, operation, key, request_data, ReviewAttemptResponse)
    if prior is not None:
        return prior
    scheduler: ReviewScheduler = request.app.state.review_scheduler
    attempt, item = record_review_attempt(
        uow, scheduler, owner_id, review_id, **body.model_dump()
    )
    response = _attempt_response(attempt, item)
    _store(uow, owner_id, operation, key, request_data, response)
    uow.commit()
    return response


@router.post("/reviews/{review_id}/dismiss", response_model=ReviewItemResponse)
def post_review_dismiss(
    review_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[NotebookReviewUnitOfWork, Depends(get_unit_of_work)],
    key: Annotated[str, Depends(idempotency_key)],
) -> ReviewItemResponse:
    operation = f"dismiss_review:{review_id}"
    prior = _prior(uow, owner_id, operation, key, {}, ReviewItemResponse)
    if prior is not None:
        return prior
    response = _review_response(
        dismiss_review_item(uow, owner_id, review_id), reveal=False
    )
    _store(uow, owner_id, operation, key, {}, response)
    uow.commit()
    return response


def _entry_response(entry: NotebookEntry) -> NotebookEntryResponse:
    return NotebookEntryResponse(
        **{
            key: value
            for key, value in entry.__dict__.items()
            if key not in {"owner_id", "tombstoned_at"}
        }
    )


def _preferences_response(value) -> ReviewPreferencesResponse:
    return ReviewPreferencesResponse(
        **{key: item for key, item in value.__dict__.items() if key != "owner_id"}
    )


def _review_response(item: ReviewItem, *, reveal: bool) -> ReviewItemResponse:
    values = {key: value for key, value in item.__dict__.items() if key != "owner_id"}
    values["answer"] = item.answer if reveal else None
    values["retryable"] = item.status is ReviewItemStatus.GENERATION_FAILED
    return ReviewItemResponse(**values)


def _attempt_response(
    attempt: ReviewAttempt, item: ReviewItem
) -> ReviewAttemptResponse:
    assert item.answer is not None
    values = {
        key: value for key, value in attempt.__dict__.items() if key != "owner_id"
    }
    return ReviewAttemptResponse(
        **values, review_status=item.status, revealed_answer=item.answer
    )


def _prior[ResponseModel: BaseModel](
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    operation: str,
    key: str,
    request_data: dict[str, object],
    response_type: type[ResponseModel],
) -> ResponseModel | None:
    prior = uow.notebook_review.get_idempotency(owner_id, operation, key)
    if prior is None:
        return None
    if prior.request_hash != hash_payload(request_data):
        raise IdempotencyConflictError(
            "The Idempotency-Key was reused with a different notebook/review request."
        )
    return response_type.model_validate_json(prior.response_json)


def _store(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    operation: str,
    key: str,
    request_data: dict[str, object],
    response: BaseModel,
) -> None:
    _store_raw(uow, owner_id, operation, key, request_data, response.model_dump_json())


def _store_raw(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    operation: str,
    key: str,
    request_data: dict[str, object],
    response_json: str,
) -> None:
    uow.notebook_review.add_idempotency(
        NotebookReviewIdempotencyRecord(
            new_id(),
            owner_id,
            operation,
            key,
            hash_payload(request_data),
            response_json,
            now_text(SystemClock()),
        )
    )

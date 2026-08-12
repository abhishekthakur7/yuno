"""Notebook and optional review application services."""

from __future__ import annotations

from collections.abc import Sequence

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.notebook_review.domain import (
    FIXTURE_SCHEDULING_VERSION,
    GoalReviewPreferences,
    NotebookEntry,
    NotebookEntryKind,
    ReviewAttempt,
    ReviewCadence,
    ReviewConfidence,
    ReviewItem,
    ReviewItemStatus,
    ReviewScheduleDecision,
    default_review_preferences,
)
from yuno.modules.notebook_review.ports import NotebookReviewUnitOfWork, ReviewScheduler
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    GoneError,
    NotFoundError,
    PreconditionFailedError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


class FixtureReviewScheduler:
    """Deterministic placeholder scheduler."""

    def schedule(
        self, item: ReviewItem, response: str, now: str
    ) -> ReviewScheduleDecision:
        if not response.strip():
            raise DomainValidationError("A review response must not be blank.")
        return ReviewScheduleDecision(
            ReviewItemStatus.COMPLETED, None, None, None, FIXTURE_SCHEDULING_VERSION
        )


def list_notebook_entries(
    uow: NotebookReviewUnitOfWork, owner_id: str, goal_id: str
) -> Sequence[NotebookEntry]:
    _goal(uow, owner_id, goal_id)
    return uow.notebook_review.list_entries(owner_id, goal_id)


def get_notebook_entry(
    uow: NotebookReviewUnitOfWork, owner_id: str, entry_id: str
) -> NotebookEntry:
    return _entry(uow, owner_id, entry_id)


def create_notebook_entry(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    goal_id: str,
    *,
    entry_kind: NotebookEntryKind,
    markdown: str,
    topic_stable_id: str | None = None,
    evidence_id: str | None = None,
    source_id: str | None = None,
    clock: Clock | None = None,
) -> NotebookEntry:
    _validate_entry_refs(
        uow, owner_id, goal_id, topic_stable_id, evidence_id, source_id
    )
    if not markdown.strip():
        raise DomainValidationError("Notebook Markdown must not be blank.")
    timestamp = now_text(clock or SystemClock())
    entry = NotebookEntry(
        new_id(),
        owner_id,
        goal_id,
        topic_stable_id,
        evidence_id,
        source_id,
        entry_kind,
        markdown,
        1,
        timestamp,
        timestamp,
        None,
    )
    uow.notebook_review.add_entry(entry)
    _audit(
        uow,
        owner_id,
        goal_id,
        "notebook_entry",
        entry.id,
        "created",
        None,
        hash_payload(entry),
        timestamp,
    )
    return entry


def update_notebook_entry(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    entry_id: str,
    *,
    expected_version: int,
    markdown: str,
    topic_stable_id: str | None,
    evidence_id: str | None,
    source_id: str | None,
    clock: Clock | None = None,
) -> NotebookEntry:
    before = _entry(uow, owner_id, entry_id)
    _validate_entry_refs(
        uow, owner_id, before.goal_id, topic_stable_id, evidence_id, source_id
    )
    if not markdown.strip():
        raise DomainValidationError("Notebook Markdown must not be blank.")
    timestamp = now_text(clock or SystemClock())
    updated = uow.notebook_review.update_entry(
        owner_id,
        entry_id,
        expected_version,
        {
            "markdown": markdown,
            "topic_stable_id": topic_stable_id,
            "evidence_id": evidence_id,
            "source_id": source_id,
            "updated_at": timestamp,
        },
    )
    if updated is None:
        raise PreconditionFailedError(
            "The notebook entry changed; reload it and retry."
        )
    _audit(
        uow,
        owner_id,
        before.goal_id,
        "notebook_entry",
        entry_id,
        "updated",
        hash_payload(before),
        hash_payload(updated),
        timestamp,
    )
    return updated


def delete_notebook_entry(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    entry_id: str,
    *,
    expected_version: int,
    clock: Clock | None = None,
) -> None:
    before = _entry(uow, owner_id, entry_id)
    timestamp = now_text(clock or SystemClock())
    updated = uow.notebook_review.update_entry(
        owner_id,
        entry_id,
        expected_version,
        {"tombstoned_at": timestamp, "updated_at": timestamp},
    )
    if updated is None:
        raise PreconditionFailedError(
            "The notebook entry changed; reload it and retry."
        )
    _audit(
        uow,
        owner_id,
        before.goal_id,
        "notebook_entry",
        entry_id,
        "tombstoned",
        hash_payload(before),
        hash_payload(updated),
        timestamp,
    )


def get_review_preferences(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    goal_id: str,
    *,
    clock: Clock | None = None,
) -> GoalReviewPreferences:
    _goal(uow, owner_id, goal_id)
    stored = uow.notebook_review.get_preferences(owner_id, goal_id)
    return stored or default_review_preferences(
        owner_id, goal_id, now_text(clock or SystemClock())
    )


def update_review_preferences(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    goal_id: str,
    *,
    expected_version: int,
    enabled: bool,
    duration_minutes: int,
    cadence: ReviewCadence,
    retrieval_enabled: bool,
    varied_context_enabled: bool,
    clock: Clock | None = None,
) -> GoalReviewPreferences:
    before = get_review_preferences(uow, owner_id, goal_id, clock=clock)
    if duration_minutes not in {10, 15, 25}:
        raise DomainValidationError("Review duration must be 10, 15, or 25 minutes.")
    timestamp = now_text(clock or SystemClock())
    desired = GoalReviewPreferences(
        owner_id,
        goal_id,
        enabled,
        duration_minutes,
        cadence,
        retrieval_enabled,
        varied_context_enabled,
        FIXTURE_SCHEDULING_VERSION,
        expected_version + 1,
        timestamp,
    )
    updated = uow.notebook_review.put_preferences(desired, expected_version)
    if updated is None:
        raise PreconditionFailedError(
            "Review preferences changed; reload them and retry."
        )
    if not enabled:
        uow.notebook_review.disable_active_review_items(owner_id, goal_id, timestamp)
    _audit(
        uow,
        owner_id,
        goal_id,
        "goal_review_preferences",
        goal_id,
        "updated",
        hash_payload(before),
        hash_payload(updated),
        timestamp,
    )
    return updated


def list_reviews(
    uow: NotebookReviewUnitOfWork, owner_id: str, goal_id: str
) -> Sequence[ReviewItem]:
    _goal(uow, owner_id, goal_id)
    return uow.notebook_review.list_review_items(owner_id, goal_id)


def create_review_item(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    goal_id: str,
    item: ReviewItem,
) -> ReviewItem:
    """Validate and persist a generated review item."""
    goal = _goal(uow, owner_id, goal_id)
    topic_ids = {
        topic.stable_id
        for topic in uow.canonical.get_published_topics(goal.graph_version_id)
    }
    if (
        item.owner_id != owner_id
        or item.goal_id != goal_id
        or item.topic_stable_id not in topic_ids
    ):
        raise DomainValidationError(
            "A review item must match the owner, goal, and approved topic."
        )
    if (
        not item.prompt.strip()
        or not item.prompt_ref.strip()
        or (
            item.status is not ReviewItemStatus.GENERATION_FAILED
            and (item.answer is None or not item.answer.strip())
        )
    ):
        raise DomainValidationError(
            "Review prompt, answer, and prompt reference must not be blank."
        )
    return uow.notebook_review.add_review_item(item)


def record_review_attempt(
    uow: NotebookReviewUnitOfWork,
    scheduler: ReviewScheduler,
    owner_id: str,
    review_id: str,
    *,
    response: str,
    confidence: ReviewConfidence | None = None,
    context_result: str | None = None,
    clock: Clock | None = None,
) -> tuple[ReviewAttempt, ReviewItem]:
    if not response.strip():
        raise DomainValidationError("A review response must not be blank.")
    item = _review_item(uow, owner_id, review_id)
    if item.status not in {ReviewItemStatus.READY, ReviewItemStatus.DUE}:
        raise ConflictError("Only a ready or due review item can be attempted.")
    timestamp = now_text(clock or SystemClock())
    decision = scheduler.schedule(item, response, timestamp)
    if decision.scheduling_version != item.scheduling_version:
        raise ConflictError("The review scheduling version changed; reload and retry.")
    attempt = ReviewAttempt(
        new_id(),
        owner_id,
        item.goal_id,
        item.id,
        response,
        confidence,
        None,
        None,
        decision.next_interval_label,
        decision.context_variation,
        context_result,
        decision.scheduling_version,
        timestamp,
    )
    uow.notebook_review.add_attempt(attempt)
    updated = uow.notebook_review.transition_review_item(
        owner_id,
        item.id,
        item.status.value,
        {
            "status": decision.status,
            "due_at": decision.due_at,
            "interval_label": decision.next_interval_label,
            "context": decision.context_variation,
            "updated_at": timestamp,
        },
    )
    if updated is None:
        raise ConflictError("The review item changed while recording the attempt.")
    _audit(
        uow,
        owner_id,
        item.goal_id,
        "review_attempt",
        attempt.id,
        "created",
        None,
        hash_payload(attempt),
        timestamp,
    )
    return attempt, updated


def dismiss_review_item(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    review_id: str,
    *,
    clock: Clock | None = None,
) -> ReviewItem:
    item = _review_item(uow, owner_id, review_id)
    if item.status not in {ReviewItemStatus.READY, ReviewItemStatus.DUE}:
        raise ConflictError("Only a ready or due review item can be dismissed.")
    timestamp = now_text(clock or SystemClock())
    updated = uow.notebook_review.transition_review_item(
        owner_id,
        review_id,
        item.status.value,
        {"status": ReviewItemStatus.DISMISSED, "updated_at": timestamp},
    )
    if updated is None:
        raise ConflictError("The review item changed while dismissing it.")
    _audit(
        uow,
        owner_id,
        item.goal_id,
        "review_item",
        item.id,
        "dismissed",
        hash_payload(item),
        hash_payload(updated),
        timestamp,
    )
    return updated


def _validate_entry_refs(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    goal_id: str,
    topic_id: str | None,
    evidence_id: str | None,
    source_id: str | None,
) -> None:
    goal = _goal(uow, owner_id, goal_id)
    if topic_id is not None and topic_id not in {
        topic.stable_id
        for topic in uow.canonical.get_published_topics(goal.graph_version_id)
    }:
        raise DomainValidationError(
            "The notebook topic is not in the goal's approved graph."
        )
    if (
        evidence_id is not None
        and uow.evidence.get_evidence(owner_id, goal_id, evidence_id) is None
    ):
        raise NotFoundError("The linked evidence was not found in this goal.")
    if source_id is not None and uow.provenance.get_source(owner_id, source_id) is None:
        raise NotFoundError("The linked source was not found.")


def _goal(uow: NotebookReviewUnitOfWork, owner_id: str, goal_id: str):
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    return goal


def _entry(
    uow: NotebookReviewUnitOfWork, owner_id: str, entry_id: str
) -> NotebookEntry:
    entry = uow.notebook_review.get_entry(owner_id, entry_id)
    if entry is None:
        raise NotFoundError(f"Notebook entry '{entry_id}' was not found.")
    if entry.tombstoned_at is not None:
        raise GoneError(f"Notebook entry '{entry_id}' is tombstoned.")
    return entry


def _review_item(
    uow: NotebookReviewUnitOfWork, owner_id: str, review_id: str
) -> ReviewItem:
    item = uow.notebook_review.get_review_item(owner_id, review_id)
    if item is None:
        raise NotFoundError(f"Review item '{review_id}' was not found.")
    return item


def _audit(
    uow: NotebookReviewUnitOfWork,
    owner_id: str,
    goal_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    before_hash: str | None,
    after_hash: str | None,
    timestamp: str,
) -> None:
    uow.audit.append(
        AuditEvent(
            new_id(),
            owner_id,
            goal_id,
            "learner",
            entity_type,
            entity_id,
            action,
            before_hash,
            after_hash,
            None,
            None,
            None,
            timestamp,
        )
    )

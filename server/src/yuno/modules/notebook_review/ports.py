"""Repository and scheduling ports for notebook/review."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.notebook_review.domain import (
    GoalReviewPreferences,
    NotebookEntry,
    NotebookReviewIdempotencyRecord,
    ReviewAttempt,
    ReviewItem,
    ReviewScheduleDecision,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class NotebookReviewRepository(Protocol):
    def add_entry(self, entry: NotebookEntry) -> NotebookEntry: ...
    def get_entry(self, owner_id: str, entry_id: str) -> NotebookEntry | None: ...
    def list_entries(self, owner_id: str, goal_id: str) -> Sequence[NotebookEntry]: ...
    def update_entry(
        self,
        owner_id: str,
        entry_id: str,
        expected_version: int,
        changes: dict[str, object],
    ) -> NotebookEntry | None: ...
    def get_preferences(
        self, owner_id: str, goal_id: str
    ) -> GoalReviewPreferences | None: ...
    def put_preferences(
        self, preferences: GoalReviewPreferences, expected_version: int
    ) -> GoalReviewPreferences | None: ...
    def add_review_item(self, item: ReviewItem) -> ReviewItem: ...
    def get_review_item(self, owner_id: str, review_id: str) -> ReviewItem | None: ...
    def list_review_items(
        self, owner_id: str, goal_id: str
    ) -> Sequence[ReviewItem]: ...
    def transition_review_item(
        self,
        owner_id: str,
        review_id: str,
        expected_status: str,
        changes: dict[str, object],
    ) -> ReviewItem | None: ...
    def disable_active_review_items(
        self, owner_id: str, goal_id: str, updated_at: str
    ) -> None: ...
    def add_attempt(self, attempt: ReviewAttempt) -> ReviewAttempt: ...
    def list_attempts(
        self, owner_id: str, review_id: str
    ) -> Sequence[ReviewAttempt]: ...
    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> NotebookReviewIdempotencyRecord | None: ...
    def add_idempotency(self, record: NotebookReviewIdempotencyRecord) -> None: ...


class ReviewScheduler(Protocol):
    def schedule(
        self, item: ReviewItem, response: str, now: str
    ) -> ReviewScheduleDecision: ...


class GoalView(Protocol):
    graph_version_id: str


class GoalRepository(Protocol):
    def get_goal(self, owner_id: str, goal_id: str) -> GoalView | None: ...


class TopicView(Protocol):
    stable_id: str


class CanonicalRepository(Protocol):
    def get_published_topics(self, version_id: str) -> Sequence[TopicView]: ...


class EvidenceView(Protocol):
    goal_id: str


class EvidenceRepository(Protocol):
    def get_evidence(
        self, owner_id: str, goal_id: str, evidence_id: str
    ) -> EvidenceView | None: ...


class SourceView(Protocol):
    id: str


class SourceReadRepository(Protocol):
    def get_source(self, owner_id: str, source_id: str) -> SourceView | None: ...


class NotebookReviewUnitOfWork(UnitOfWork, Protocol):
    notebook_review: NotebookReviewRepository
    profiles_goals: GoalRepository
    canonical: CanonicalRepository
    evidence: EvidenceRepository
    provenance: SourceReadRepository
    audit: AuditRepository

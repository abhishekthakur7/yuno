"""Framework-free notebook and review domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

FIXTURE_SCHEDULING_VERSION = "fixture-v0"


class NotebookEntryKind(StrEnum):
    AUTO = "auto"
    USER = "user"


class ReviewPromptType(StrEnum):
    RECALL = "recall"
    EXPLANATION = "explanation"
    APPLICATION = "application"


class ReviewItemStatus(StrEnum):
    READY = "ready"
    DUE = "due"
    DISMISSED = "dismissed"
    DISABLED = "disabled"
    GENERATION_FAILED = "generation-failed"
    COMPLETED = "completed"


class ReviewCadence(StrEnum):
    ONCE_WEEKLY = "once-weekly"
    TWICE_WEEKLY = "twice-weekly"
    THREE_TIMES_WEEKLY = "three-times-weekly"


class ReviewConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class NotebookEntry:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str | None
    evidence_id: str | None
    source_id: str | None
    entry_kind: NotebookEntryKind
    markdown: str
    row_version: int
    created_at: str
    updated_at: str
    tombstoned_at: str | None


@dataclass(frozen=True)
class GoalReviewPreferences:
    owner_id: str
    goal_id: str
    enabled: bool
    duration_minutes: int
    cadence: ReviewCadence
    retrieval_enabled: bool
    varied_context_enabled: bool
    scheduling_version: str
    row_version: int
    updated_at: str


@dataclass(frozen=True)
class ReviewItem:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    prompt_ref: str
    prompt_type: ReviewPromptType
    prompt: str
    answer: str | None
    status: ReviewItemStatus
    due_at: str | None
    interval_label: str | None
    context: str | None
    scheduling_version: str
    failure_reference: str | None
    row_version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ReviewAttempt:
    id: str
    owner_id: str
    goal_id: str
    review_item_id: str
    response: str
    confidence: ReviewConfidence | None
    feedback: str | None
    correction: str | None
    next_interval_label: str | None
    context_variation: str | None
    context_result: str | None
    scheduling_version: str
    created_at: str


@dataclass(frozen=True)
class ReviewScheduleDecision:
    status: ReviewItemStatus
    due_at: str | None
    next_interval_label: str | None
    context_variation: str | None
    scheduling_version: str


@dataclass(frozen=True)
class NotebookReviewIdempotencyRecord:
    id: str
    owner_id: str
    operation: str
    idempotency_key: str
    request_hash: str
    response_json: str
    created_at: str


def default_review_preferences(
    owner_id: str, goal_id: str, now: str
) -> GoalReviewPreferences:
    return GoalReviewPreferences(
        owner_id,
        goal_id,
        True,
        15,
        ReviewCadence.TWICE_WEEKLY,
        True,
        True,
        FIXTURE_SCHEDULING_VERSION,
        1,
        now,
    )

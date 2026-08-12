"""Framework-free interview bundle contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BundleSubject(StrEnum):
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    LEADERSHIP = "leadership"


class PracticeRunState(StrEnum):
    READY = "ready"
    ANSWERING = "answering"
    FOLLOW_UP = "follow-up"
    SUBMITTED = "submitted"
    EVALUATING = "evaluating"
    FEEDBACK_READY = "feedback-ready"
    FAILED_RECOVERABLE = "failed-recoverable"


class MockRunState(StrEnum):
    READY = "ready"
    ANSWERING = "answering"
    FOLLOW_UP = "follow-up"
    PAUSED = "paused"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED_RECOVERABLE = "failed-recoverable"


class InterviewTurnKind(StrEnum):
    QUESTION = "question"
    ANSWER = "answer"
    HINT = "hint"
    FOLLOW_UP = "follow-up"


@dataclass(frozen=True)
class PracticeTurn:
    id: str
    owner_id: str
    run_id: str
    turn_number: int
    kind: InterviewTurnKind
    body: str
    answer_turn_id: str | None
    evidence_id: str | None
    created_at: str


@dataclass(frozen=True)
class PracticeDimensionResult:
    dimension_id: str
    name: str
    outcome: str
    rationale: str


@dataclass(frozen=True)
class PracticeTurnResult:
    id: str
    owner_id: str
    run_id: str
    answer_turn_id: str
    assessment_id: str
    visible_at: str
    facts: tuple[str, ...]
    trade_offs: tuple[str, ...]
    dimensions: tuple[PracticeDimensionResult, ...]
    feedback: str
    cross_question_candidate: str | None


@dataclass(frozen=True)
class PracticeRun:
    id: str
    owner_id: str
    goal_id: str
    bundle_id: str
    bundle_item_id: str
    mode: str
    state: PracticeRunState | MockRunState
    question: str
    hint_text: str | None
    rubric_id: str | None
    rubric_version: str | None
    requested_capability: str
    active_job_id: str | None
    active_answer_turn_id: str | None
    failure_reference: str | None
    retryable: bool
    draft: str
    final_assessment_id: str | None
    created_at: str
    updated_at: str
    turns: tuple[PracticeTurn, ...]
    results: tuple[PracticeTurnResult, ...]


@dataclass(frozen=True)
class InterviewBundleItem:
    id: str
    owner_id: str
    bundle_id: str
    subject: BundleSubject
    topic_stable_id: str | None
    question: str | None
    position: int
    is_optional: bool
    included: bool


@dataclass(frozen=True)
class InterviewBundle:
    id: str
    owner_id: str
    goal_id: str | None
    name: str
    generic_role: str
    target_level: str
    origin: str
    copy_source_id: str | None
    status: str
    row_version: int
    created_at: str
    updated_at: str
    items: tuple[InterviewBundleItem, ...]


@dataclass(frozen=True)
class InterviewIdempotencyRecord:
    id: str
    owner_id: str
    operation: str
    idempotency_key: str
    request_hash: str
    response_json: str
    created_at: str

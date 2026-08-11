"""Diagnostic entities, lifecycle, and adaptive question selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from yuno.shared.domain.errors import ConflictError, DomainValidationError

QUESTION_SET_VERSION = "diagnostic-fixture-v1"


class DiagnosticPath(StrEnum):
    LEARN = "learn"
    INTERVIEW_PREP = "interview_prep"


class DiagnosticTargetLevel(StrEnum):
    MID_LEVEL = "Mid-level"
    SENIOR = "Senior"
    STAFF = "Staff"


class DiagnosticTargetCapability(StrEnum):
    KNOW = "know"
    UNDERSTAND = "understand"
    CHOOSE = "choose"
    IMPLEMENT = "implement"
    DIAGNOSE = "diagnose"
    DEFEND = "defend"


class DiagnosticState(StrEnum):
    NOT_STARTED = "not-started"
    IN_PROGRESS = "in-progress"
    PAUSED = "paused"
    SKIPPED = "skipped"
    RESUMED = "resumed"
    ROADMAP_PREVIEW = "roadmap-preview"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class DiagnosticConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UntrustedSeedKind(StrEnum):
    LEARN_NOTES = "notes"
    INTERVIEW_QUESTIONS = "questions"


class DiagnosticAction(StrEnum):
    PAUSE = "pause"
    RESUME = "resume"
    SKIP_DIAGNOSTIC = "skip_diagnostic"
    SKIP_SEED = "skip_notes"
    OPEN_ROADMAP_PREVIEW = "open_roadmap_preview"
    RETRY = "retry"


@dataclass(frozen=True)
class DiagnosticSession:
    id: str
    owner_id: str
    captured_graph_version_id: str
    question_set_version: str
    setup_inputs: Mapping[str, object]
    state: DiagnosticState
    untrusted_seed_kind: UntrustedSeedKind | None
    untrusted_seed_text: str | None
    seed_skipped: bool
    diagnostic_skipped: bool
    started_at: str | None
    paused_at: str | None
    expires_at: str | None
    failure_code: str | None
    failure_reference: str | None
    confirmed_goal_id: str | None
    row_version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class DiagnosticAnswer:
    id: str
    owner_id: str
    session_id: str
    sequence: int
    question_ref: str
    answer: str
    confidence: DiagnosticConfidence
    adaptive_context_version: str
    answered_at: str


@dataclass(frozen=True)
class DiagnosticQuestion:
    ref: str
    prompt: str
    sequence: int
    adaptive_context_version: str = QUESTION_SET_VERSION


@dataclass(frozen=True)
class DiagnosticsIdempotencyRecord:
    id: str
    owner_id: str
    operation: str
    idempotency_key: str
    request_hash: str
    session_id: str
    response_json: str
    created_at: str


@dataclass(frozen=True)
class DiagnosticPreviewEdit:
    id: str
    owner_id: str
    session_id: str
    sequence: int
    topic_stable_id: str | None
    entry_type: str
    value: Mapping[str, object]
    reason: str | None
    updated_at: str


def validate_setup_inputs(setup_inputs: Mapping[str, object]) -> None:
    path = DiagnosticPath(str(setup_inputs.get("path", "")))
    subject = setup_inputs.get("subject")
    role = setup_inputs.get("role")
    if path is DiagnosticPath.LEARN:
        if not isinstance(subject, str) or not subject.strip():
            raise DomainValidationError("A Learn diagnostic requires a subject.")
        if role is not None:
            raise DomainValidationError("A Learn diagnostic must not specify a role.")
    else:
        if not isinstance(role, str) or not role.strip():
            raise DomainValidationError("An Interview Prep diagnostic requires a role.")
        if subject is not None:
            raise DomainValidationError(
                "An Interview Prep diagnostic must not specify a subject."
            )


def next_question(
    session: DiagnosticSession, answers: Sequence[DiagnosticAnswer]
) -> DiagnosticQuestion | None:
    """Select the next question using only persisted answer context."""
    if session.question_set_version != QUESTION_SET_VERSION:
        raise ConflictError(
            f"Diagnostic question set '{session.question_set_version}' is unavailable.",
            current_state=session.state.value,
        )
    if any(
        answer.adaptive_context_version != session.question_set_version
        for answer in answers
    ):
        raise ConflictError(
            "The saved diagnostic answers do not match the session's question set.",
            current_state=session.state.value,
        )
    if session.diagnostic_skipped or len(answers) >= 3:
        return None
    path = DiagnosticPath(str(session.setup_inputs["path"]))
    if not answers:
        if path is DiagnosticPath.LEARN:
            prompt = (
                "Describe what you already understand about your chosen subject "
                "and one part you would want to verify."
            )
            ref = "learn-baseline"
        else:
            prompt = (
                "Describe how you would approach a representative backend "
                "interview problem and where you feel least certain."
            )
            ref = "interview-baseline"
        return DiagnosticQuestion(ref=ref, prompt=prompt, sequence=1)

    if len(answers) == 1:
        prior = answers[-1]
        normalized = prior.answer.casefold()
        uncertain = ("don't know", "dont know", "unsure", "not sure", "guess")
        depth = (
            "trade-off",
            "tradeoff",
            "failure",
            "latency",
            "consistency",
            "idempot",
        )
        score = {
            DiagnosticConfidence.LOW: -1,
            DiagnosticConfidence.MEDIUM: 0,
            DiagnosticConfidence.HIGH: 1,
        }[prior.confidence]
        score += int(any(marker in normalized for marker in depth))
        score -= int(any(marker in normalized for marker in uncertain))
        if score <= -1:
            return DiagnosticQuestion(
                ref="foundation-follow-up",
                prompt="What foundational concept would help you reason about that answer?",
                sequence=2,
            )
        if score >= 1:
            return DiagnosticQuestion(
                ref="depth-follow-up",
                prompt="Which trade-off or failure mode would change your approach?",
                sequence=2,
            )
        return DiagnosticQuestion(
            ref="application-follow-up",
            prompt="Give a concrete example of applying that reasoning.",
            sequence=2,
        )

    return DiagnosticQuestion(
        ref="reflection",
        prompt="What would you test or verify before relying on your answer?",
        sequence=3,
    )


def validate_answer(
    session: DiagnosticSession,
    answers: Sequence[DiagnosticAnswer],
    *,
    question_ref: str,
    answer: str,
) -> DiagnosticQuestion:
    if session.state not in {DiagnosticState.IN_PROGRESS, DiagnosticState.RESUMED}:
        raise ConflictError(
            "Answers can only be added to an active diagnostic.",
            current_state=session.state.value,
        )
    if not answer.strip():
        raise DomainValidationError("A diagnostic answer must not be blank.")
    expected = next_question(session, answers)
    if expected is None:
        raise ConflictError(
            "This diagnostic has no remaining questions.",
            current_state=session.state.value,
        )
    if question_ref != expected.ref:
        raise ConflictError(
            f"Expected answer for question '{expected.ref}'.",
            current_state=session.state.value,
        )
    return expected

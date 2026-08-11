"""Application services for persisted optional diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.diagnostics.domain import (
    QUESTION_SET_VERSION,
    DiagnosticAction,
    DiagnosticAnswer,
    DiagnosticConfidence,
    DiagnosticPath,
    DiagnosticSession,
    DiagnosticState,
    UntrustedSeedKind,
    next_question,
    validate_answer,
    validate_setup_inputs,
)
from yuno.modules.diagnostics.ports import DiagnosticsUnitOfWork
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


def create_diagnostic(
    uow: DiagnosticsUnitOfWork,
    owner_id: str,
    *,
    captured_graph_version_id: str,
    setup_inputs: Mapping[str, object],
    approved_graph_exists: bool,
    expires_at: str | None = None,
    clock: Clock | None = None,
) -> DiagnosticSession:
    validate_setup_inputs(setup_inputs)
    if not approved_graph_exists:
        raise NotFoundError("The approved canonical graph version was not found.")
    timestamp = now_text(clock or SystemClock())
    session = DiagnosticSession(
        id=new_id(),
        owner_id=owner_id,
        captured_graph_version_id=captured_graph_version_id,
        question_set_version=QUESTION_SET_VERSION,
        setup_inputs=dict(setup_inputs),
        state=DiagnosticState.IN_PROGRESS,
        untrusted_seed_kind=None,
        untrusted_seed_text=None,
        seed_skipped=False,
        diagnostic_skipped=False,
        started_at=timestamp,
        paused_at=None,
        expires_at=expires_at,
        failure_code=None,
        failure_reference=None,
        confirmed_goal_id=None,
        row_version=1,
        created_at=timestamp,
        updated_at=timestamp,
    )
    created = uow.diagnostics.create_session(session)
    _audit(uow, owner_id, created.id, "created", None, created, clock)
    return created


def get_diagnostic(
    uow: DiagnosticsUnitOfWork,
    owner_id: str,
    session_id: str,
    *,
    clock: Clock | None = None,
) -> DiagnosticSession:
    session = uow.diagnostics.get_session(owner_id, session_id)
    if session is None:
        raise NotFoundError(f"Diagnostic '{session_id}' was not found.")
    _require_not_expired(session, clock or SystemClock())
    return session


def patch_diagnostic(
    uow: DiagnosticsUnitOfWork,
    owner_id: str,
    session_id: str,
    expected_version: int,
    *,
    action: DiagnosticAction | None,
    untrusted_seed_text: str | None,
    seed_was_supplied: bool,
    clock: Clock | None = None,
) -> DiagnosticSession:
    active_clock = clock or SystemClock()
    before = get_diagnostic(uow, owner_id, session_id, clock=active_clock)
    if before.row_version != expected_version:
        raise PreconditionFailedError(
            "The diagnostic has changed; reload it and retry."
        )
    if action is None and not seed_was_supplied:
        raise DomainValidationError(
            "A diagnostic PATCH must include an action or optional notes/questions."
        )
    if seed_was_supplied and before.state not in {
        DiagnosticState.IN_PROGRESS,
        DiagnosticState.RESUMED,
    }:
        raise ConflictError(
            "Optional notes/questions can only be changed during an active diagnostic.",
            current_state=before.state.value,
        )
    if seed_was_supplied and action is DiagnosticAction.SKIP_SEED:
        raise DomainValidationError(
            "Save optional notes/questions or skip them, but not both at once."
        )
    changes: dict[str, object] = {}
    timestamp = now_text(active_clock)

    if seed_was_supplied:
        if untrusted_seed_text is None or not untrusted_seed_text.strip():
            raise DomainValidationError(
                "Optional notes/questions must not be blank; skip the step instead."
            )
        if before.seed_skipped:
            raise ConflictError(
                "The optional notes/questions step was already skipped.",
                current_state=before.state.value,
            )
        changes["untrusted_seed_text"] = untrusted_seed_text
        changes["untrusted_seed_kind"] = (
            UntrustedSeedKind.LEARN_NOTES
            if before.setup_inputs["path"] == DiagnosticPath.LEARN.value
            else UntrustedSeedKind.INTERVIEW_QUESTIONS
        )

    if action is not None:
        if action is DiagnosticAction.OPEN_ROADMAP_PREVIEW:
            if not before.seed_skipped and before.untrusted_seed_text is None:
                raise ConflictError(
                    "Save or skip optional notes/questions before opening the roadmap preview.",
                    current_state=before.state.value,
                )
            answers = tuple(uow.diagnostics.list_answers(owner_id, session_id))
            if before.state is not DiagnosticState.SKIPPED and next_question(
                before, answers
            ) is not None:
                raise ConflictError(
                    "Finish or skip the diagnostic before opening its roadmap preview.",
                    current_state=before.state.value,
                )
        changes.update(_transition(before, action, timestamp))
    if not changes:
        return before
    changes["updated_at"] = timestamp
    updated = uow.diagnostics.update_session(
        owner_id, session_id, expected_version, changes
    )
    if updated is None:
        raise PreconditionFailedError(
            "The diagnostic has changed; reload it and retry."
        )
    _audit(uow, owner_id, session_id, "updated", before, updated, active_clock)
    return updated


def append_diagnostic_answer(
    uow: DiagnosticsUnitOfWork,
    owner_id: str,
    session_id: str,
    *,
    question_ref: str,
    answer: str,
    confidence: DiagnosticConfidence,
    clock: Clock | None = None,
) -> DiagnosticAnswer:
    active_clock = clock or SystemClock()
    session = get_diagnostic(uow, owner_id, session_id, clock=active_clock)
    answers = tuple(uow.diagnostics.list_answers(owner_id, session_id))
    question = validate_answer(
        session, answers, question_ref=question_ref, answer=answer
    )
    recorded = uow.diagnostics.append_answer(
        DiagnosticAnswer(
            id=new_id(),
            owner_id=owner_id,
            session_id=session_id,
            sequence=question.sequence,
            question_ref=question.ref,
            answer=answer.strip(),
            confidence=confidence,
            adaptive_context_version=QUESTION_SET_VERSION,
            answered_at=now_text(active_clock),
        )
    )
    bumped = uow.diagnostics.update_session(
        owner_id,
        session_id,
        session.row_version,
        {},
    )
    if bumped is None:
        raise PreconditionFailedError(
            "The diagnostic changed while its answer was being saved; retry."
        )
    _audit(
        uow,
        owner_id,
        recorded.id,
        "answer_appended",
        None,
        replace(recorded, answer="[redacted]"),
        active_clock,
        entity_type="diagnostic_answer",
    )
    return recorded


def record_diagnostic_failure(
    uow: DiagnosticsUnitOfWork,
    owner_id: str,
    session_id: str,
    *,
    failure_code: str,
    failure_reference: str | None,
    clock: Clock | None = None,
) -> DiagnosticSession:
    before = get_diagnostic(uow, owner_id, session_id, clock=clock)
    active_clock = clock or SystemClock()
    updated = uow.diagnostics.update_session(
        owner_id,
        session_id,
        before.row_version,
        {
            "state": DiagnosticState.FAILED,
            "failure_code": failure_code,
            "failure_reference": failure_reference,
            "updated_at": now_text(active_clock),
        },
    )
    if updated is None:
        raise PreconditionFailedError(
            "The diagnostic has changed; reload it and retry."
        )
    _audit(uow, owner_id, session_id, "failed", before, updated, active_clock)
    return updated


def _transition(
    session: DiagnosticSession, action: DiagnosticAction, timestamp: str
) -> Mapping[str, object]:
    state = session.state
    if state in {DiagnosticState.ROADMAP_PREVIEW, DiagnosticState.CONFIRMED}:
        raise ConflictError(
            "The diagnostic can no longer be changed.", current_state=state.value
        )
    if action is DiagnosticAction.PAUSE:
        if state not in {DiagnosticState.IN_PROGRESS, DiagnosticState.RESUMED}:
            raise ConflictError(
                "Only an active diagnostic can be paused.", current_state=state.value
            )
        return {"state": DiagnosticState.PAUSED, "paused_at": timestamp}
    if action is DiagnosticAction.RESUME:
        if state not in {DiagnosticState.PAUSED, DiagnosticState.SKIPPED}:
            raise ConflictError(
                "This diagnostic cannot be resumed.", current_state=state.value
            )
        return {
            "state": DiagnosticState.RESUMED,
            "paused_at": None,
            "diagnostic_skipped": False,
        }
    if action is DiagnosticAction.RETRY:
        if state is not DiagnosticState.FAILED:
            raise ConflictError(
                "Only a failed diagnostic can be retried.", current_state=state.value
            )
        return {
            "state": DiagnosticState.RESUMED,
            "failure_code": None,
            "failure_reference": None,
            "paused_at": None,
        }
    if action is DiagnosticAction.SKIP_DIAGNOSTIC:
        if state not in {
            DiagnosticState.IN_PROGRESS,
            DiagnosticState.RESUMED,
            DiagnosticState.PAUSED,
            DiagnosticState.FAILED,
        }:
            raise ConflictError(
                "This diagnostic cannot be skipped from its current state.",
                current_state=state.value,
            )
        return {"state": DiagnosticState.SKIPPED, "diagnostic_skipped": True}
    if action is DiagnosticAction.SKIP_SEED:
        if session.seed_skipped or session.untrusted_seed_text is not None:
            raise ConflictError(
                "The optional notes/questions step is already resolved.",
                current_state=state.value,
            )
        return {
            "seed_skipped": True,
            "untrusted_seed_kind": None,
            "untrusted_seed_text": None,
        }
    if action is DiagnosticAction.OPEN_ROADMAP_PREVIEW:
        if state not in {
            DiagnosticState.IN_PROGRESS,
            DiagnosticState.RESUMED,
            DiagnosticState.PAUSED,
            DiagnosticState.SKIPPED,
        }:
            raise ConflictError(
                "This diagnostic cannot open a roadmap preview from its current state.",
                current_state=state.value,
            )
        return {"state": DiagnosticState.ROADMAP_PREVIEW}
    raise AssertionError(f"Unhandled diagnostic action: {action}")


def _require_not_expired(session: DiagnosticSession, clock: Clock) -> None:
    if session.expires_at is None:
        return
    expires_at = datetime.fromisoformat(session.expires_at)
    if expires_at <= clock.now().astimezone(UTC):
        raise GoneError(
            "The diagnostic has expired.", current_state=session.state.value
        )


def _audit(
    uow: DiagnosticsUnitOfWork,
    owner_id: str,
    entity_id: str,
    action: str,
    before: object | None,
    after: object,
    clock: Clock | None,
    *,
    entity_type: str = "diagnostic_session",
) -> None:
    uow.audit.append(
        AuditEvent(
            id=new_id(),
            owner_id=owner_id,
            goal_id=None,
            actor_role="learner",
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_hash=hash_payload(before) if before is not None else None,
            after_hash=hash_payload(after),
            reason=None,
            request_id=None,
            correlation_id=None,
            occurred_at=now_text(clock or SystemClock()),
        )
    )

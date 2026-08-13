"""One-process durable worker with one reserved claim loop per lane."""

from __future__ import annotations

import fcntl
import json
import os
import signal
import threading
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.audit.repository import SqlAlchemyAuditRepository
from yuno.modules.jobs_events.repository import JobRepository, as_attempt, as_ref
from yuno.shared.application.jobs import (
    JobCancelled,
    JobCompletion,
    JobExecution,
    JobHandler,
    JobLane,
    JobPreparedFailure,
    JobRef,
    JobRequest,
    JobStatus,
)
from yuno.shared.domain.clock import Clock, SystemClock, utc_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    IdempotencyConflictError,
    NotFoundError,
    PendingJobCapError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id
from yuno.shared.infrastructure.processes import (
    process_identity,
    terminate_process_group,
)
from yuno.shared.infrastructure.structured_logging import log_event

_INTERACTIVE_KINDS = {
    "assess_evidence",
    "reevaluate_assessment",
    "evaluate_practice_answer",
    "generate_mock_next_turn",
    "evaluate_mock_final",
    "tutor_turn",
    "review_hands_on_artifact",
}

_RETRY_POLICIES = {
    "parse_import": "idempotent",
    "reprocess_import": "idempotent",
    "rebuild_index": "idempotent",
    "export_data": "idempotent",
    "delete_goal": "idempotent",
    "generate_topic_content": "generation",
    "assess_evidence": "idempotent",
    "reevaluate_assessment": "idempotent",
    "evaluate_practice_answer": "interview",
    "generate_mock_next_turn": "interview",
    "evaluate_mock_final": "interview",
    "tutor_turn": "idempotent",
    "review_hands_on_artifact": "idempotent",
    "retrieve_source_snapshot": "idempotent",
    "java_runner": "runner",
}


class DurableJobDispatcher:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        pending_cap: int | Callable[[], int],
        background_age_promotion_seconds: int | Callable[[], int],
        janitor_retention_seconds: int | Callable[[], int],
        record_workspace_cleanup: (
            Callable[[Session, str, str | None, str], str | None] | None
        ) = None,
        execute_external_cleanup: Callable[[str], None] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._sessions = session_factory
        self._pending_cap = _provider(pending_cap)
        self._promotion_seconds = _provider(background_age_promotion_seconds)
        self._retention_seconds = _provider(janitor_retention_seconds)
        self._record_cleanup = record_workspace_cleanup
        self._execute_external_cleanup = execute_external_cleanup
        self._clock = clock or SystemClock()
        self._handlers: dict[str, JobHandler] = {}
        self._wake = threading.Condition()
        self._transition_lock = threading.RLock()
        self._stop = False
        self._threads: list[threading.Thread] = []
        self._worker_id = f"worker-{os.getpid()}"
        self._janitor_diagnostic: str | None = None
        self._lane_diagnostics: dict[JobLane, str] = {}
        self._ownership_file = None

    @property
    def configuration(self) -> dict[str, int]:
        return {
            "pending_job_cap": self._pending_cap(),
            "background_age_promotion_seconds": self._promotion_seconds(),
            "janitor_retention_seconds": self._retention_seconds(),
        }

    @property
    def lane_diagnostics(self) -> dict[JobLane, str]:
        return dict(self._lane_diagnostics)

    def register(self, kind: str, handler: JobHandler) -> None:
        self._handlers[kind] = handler

    def start(self) -> None:
        if self._threads:
            return
        self._acquire_ownership()
        try:
            self.reconcile_startup()
        except Exception:
            self.stop()
            raise
        for lane in JobLane:
            thread = threading.Thread(
                target=self._run_lane,
                args=(lane,),
                name=f"jobs-{lane.value}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        with self._wake:
            self._stop = True
            self._wake.notify_all()
        for thread in self._threads:
            thread.join(timeout=5)
        self._threads.clear()
        if self._ownership_file is not None:
            fcntl.flock(self._ownership_file.fileno(), fcntl.LOCK_UN)
            self._ownership_file.close()
            self._ownership_file = None

    def _acquire_ownership(self) -> None:
        database = self._sessions.kw["bind"].url.database
        if not database or database == ":memory:":
            return
        lock_path = Path(database).with_suffix(Path(database).suffix + ".worker.lock")
        lock_file = lock_path.open("a+")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_file.close()
            raise RuntimeError(
                "Another durable worker process owns this database."
            ) from exc
        self._ownership_file = lock_file

    def enqueue(self, request: JobRequest) -> JobRef:
        with self._transition_lock, self._sessions() as session:
            ref = self.reserve(session, request)
            session.commit()
            row = JobRepository(session, self._clock).get(request.owner_id, ref.job_id)
            if row is not None:
                self._log_transition(row, "enqueued")
        with self._wake:
            self._wake.notify_all()
        return ref

    def reserve(self, session: Session, request: JobRequest) -> JobRef:
        """Write a queued job into the caller's transaction without executing it."""
        if request.kind not in self._handlers:
            raise DomainValidationError(
                f"No handler is registered for job kind {request.kind!r}."
            )
        try:
            payload_hash = hash_payload(request.payload)
        except Exception as exc:
            raise DomainValidationError(
                f"Job payload for kind {request.kind!r} could not be canonicalised for hashing ({type(exc).__name__}); it must be JSON-serialisable."
            ) from exc
        lane = request.lane or (
            JobLane.INTERACTIVE
            if request.kind in _INTERACTIVE_KINDS
            else JobLane.BACKGROUND
        )
        with self._transition_lock:
            repo = JobRepository(session, self._clock)
            if request.idempotency_key:
                existing = repo.find_idempotency(
                    request.owner_id, request.idempotency_key
                )
                if existing:
                    if existing.payload_hash != payload_hash:
                        raise IdempotencyConflictError(
                            f"Idempotency key {request.idempotency_key!r} was reused with a different request payload."
                        )
                    return as_ref(existing, deduplicated=True)
            if request.dedupe_key:
                existing = repo.find_active_dedupe(
                    request.owner_id, request.kind, request.dedupe_key
                )
                if existing:
                    return as_ref(existing, deduplicated=True)
            pending_cap = self._pending_cap()
            if repo.pending_count(request.owner_id) >= pending_cap:
                raise PendingJobCapError(
                    f"The configured pending-job cap ({pending_cap}) has been reached.",
                    recovery_action="Wait for a pending job to finish or cancel one.",
                )
            savepoint = session.begin_nested()
            try:
                row = repo.enqueue(request, lane)
                self._audit(session, row, "enqueued", None, row.state)
                savepoint.commit()
            except IntegrityError:
                savepoint.rollback()
                if request.dedupe_key and (
                    existing := repo.find_active_dedupe(
                        request.owner_id, request.kind, request.dedupe_key
                    )
                ):
                    return as_ref(existing, deduplicated=True)
                raise
        return as_ref(row)

    def get(self, owner_id: str, job_id: str) -> JobRef | None:
        with self._sessions() as session:
            row = JobRepository(session, self._clock).get(owner_id, job_id)
            return as_ref(row) if row else None

    def list(self, owner_id: str) -> tuple[JobRef, ...]:
        with self._sessions() as session:
            return tuple(
                as_ref(row)
                for row in JobRepository(session, self._clock).list(owner_id)
            )

    def attempts(self, owner_id: str, job_id: str):
        with self._sessions() as session:
            repo = JobRepository(session, self._clock)
            if repo.get(owner_id, job_id) is None:
                raise NotFoundError("The requested job was not found.")
            return tuple(
                as_attempt(row) for row in repo.list_attempts(owner_id, job_id)
            )

    def cancel(self, owner_id: str, job_id: str) -> JobRef:
        with self._transition_lock, self._sessions() as session:
            repo = JobRepository(session, self._clock)
            row = repo.get(owner_id, job_id)
            if row is None:
                raise NotFoundError("The requested job was not found.")
            repo.cancel(row)
            self._audit(session, row, "cancelled-or-requested", None, row.state)
            session.commit()
            self._log_transition(row, row.state)
            ref = as_ref(row)
        if ref.status is JobStatus.CANCEL_REQUESTED:
            self._signal_running_attempt(job_id)
        return ref

    def retry(
        self,
        owner_id: str,
        job_id: str,
        *,
        substitution_ref: str | None = None,
        confirmation_ref: str | None = None,
        provider_name: str | None = None,
        disclosure_ref: str | None = None,
    ) -> JobRef:
        with self._transition_lock, self._sessions() as session:
            repo = JobRepository(session, self._clock)
            row = repo.get(owner_id, job_id)
            if row is None:
                raise NotFoundError("The requested job was not found.")
            if row.state != "failed" or not row.retryable:
                raise ConflictError(
                    "Only a retryable failed job can be retried.",
                    current_state=row.state,
                    job_id=row.id,
                )
            if existing := repo.committed_result_for_dedupe(row):
                repo.adopt_committed_result(row, existing)
                self._audit(session, row, "cache-short-circuit", "failed", row.state)
                session.commit()
                return as_ref(row, deduplicated=True)
            strategy = _retry_policy(row.kind)
            if strategy == "runner":
                raise ConflictError(
                    "Runner jobs cannot use generic retry; create a freshly confirmed run.",
                    recovery_action="Confirm exact current inputs and create a new runner run.",
                )
            if strategy == "interview" and not substitution_ref:
                raise ConflictError(
                    "Interview retry requires an explicit substitution reference.",
                    recovery_action="Choose the substituted turn before retrying.",
                )
            repo.requeue(
                row,
                substitution_ref=substitution_ref,
                confirmation_ref=confirmation_ref,
                provider_name=provider_name,
                disclosure_ref=disclosure_ref,
                event_type={
                    "idempotent": "idempotent-rerun",
                    "generation": "cache-checked-rerun",
                    "interview": "resume-with-substitution",
                    "runner": "user-confirmed-fresh-run",
                }[strategy],
            )
            self._audit(session, row, "retried", "failed", row.state)
            session.commit()
        with self._wake:
            self._wake.notify_all()
        return as_ref(row)

    def reconcile(self, owner_id: str, job_id: str) -> JobRef:
        with self._transition_lock, self._sessions() as session:
            repo = JobRepository(session, self._clock)
            row = repo.get(owner_id, job_id)
            if row is None:
                raise NotFoundError("The requested job was not found.")
            if row.state in ("running", "cancel-requested"):
                if row.worker_id == self._worker_id and row.state == "running":
                    raise ConflictError(
                        "The current worker still owns this running attempt.",
                        current_state=row.state,
                        job_id=row.id,
                    )
                diagnostic = self._reconcile_attempt(repo, row.id)
                repo.reconcile_row(row, diagnostic)
                self._audit(session, row, "reconciled", None, row.state)
                session.commit()
            return as_ref(row)

    def reconcile_startup(self) -> None:
        with self._transition_lock, self._sessions() as session:
            repo = JobRepository(session, self._clock)
            for row in repo.startup_rows():
                diagnostic = self._reconcile_attempt(repo, row.id)
                if diagnostic:
                    raise RuntimeError(
                        f"Startup reconciliation failed for job {row.id}: {diagnostic}"
                    )
                repo.reconcile_row(row)
            session.commit()
        self._run_janitor()

    def _run_lane(self, lane: JobLane) -> None:
        while True:
            with self._wake:
                if self._stop:
                    return
            try:
                row = self._claim(lane)
            except Exception as exc:  # noqa: BLE001 -- preserve reserved-lane availability
                self._lane_diagnostics[lane] = f"{type(exc).__name__}: {exc}"
                with self._wake:
                    self._wake.wait(timeout=0.1)
                continue
            if row is None:
                with self._wake:
                    self._wake.wait(timeout=0.1)
                continue
            handler = self._handlers.get(row.kind)
            request = JobRequest(
                kind=row.kind,
                owner_id=row.owner_id,
                payload=json.loads(row.payload_json),
                dedupe_key=row.dedupe_key,
                idempotency_key=row.idempotency_key,
                requested_job_id=row.id,
                goal_id=row.goal_id,
                lane=JobLane(row.lane),
                schema_version=row.schema_version,
                request_ref=row.request_ref,
                disclosure_ref=row.disclosure_ref,
                provider_name=row.provider_name,
                confirmation_ref=row.confirmation_ref,
                correlation_id=row.correlation_id,
                request_id=row.request_id,
                run_id=row.run_id,
            )
            try:
                if handler is None:
                    raise RuntimeError(f"No handler is registered for {row.kind!r}.")
                owner_id, job_id = row.owner_id, row.id
                execution = JobExecution(
                    request=request,
                    cancel_requested=lambda owner_id=owner_id, job_id=job_id: (
                        self._is_cancel_requested(owner_id, job_id)
                    ),
                    record_runtime=lambda owner_id=owner_id, job_id=job_id, **metadata: (
                        self._record_runtime(owner_id, job_id, **metadata)
                    ),
                )
                execution.checkpoint()
                completion = handler(execution)
                execution.checkpoint()
                if not isinstance(completion, JobCompletion):
                    raise TypeError(
                        f"Job handler {row.kind!r} returned no typed JobCompletion."
                    )
                result = completion.result
                if result.kind != row.kind:
                    raise RuntimeError(
                        "Job result kind does not match the request kind."
                    )
            except JobCancelled as exc:
                with self._transition_lock, self._sessions() as session:
                    repo = JobRepository(session, self._clock)
                    current = repo.get(row.owner_id, row.id)
                    if current:
                        repo.finish_failure(current, str(exc), retryable=False)
                        self._audit(
                            session, current, "cancelled", "running", current.state
                        )
                        session.commit()
                        self._log_transition(current, "cancelled")
            except Exception as exc:  # noqa: BLE001 -- handler failures are isolated
                with self._transition_lock, self._sessions() as session:
                    repo = JobRepository(session, self._clock)
                    current = repo.get(row.owner_id, row.id)
                    if current:
                        repo.finish_failure(current, f"{type(exc).__name__}: {exc}")
                        self._audit(
                            session, current, "failed", "running", current.state
                        )
                        session.commit()
                        self._log_transition(
                            current,
                            "failed",
                            diagnostic_classification="job-handler-failure",
                        )
            else:
                try:
                    with self._transition_lock, self._sessions() as session:
                        if session.get_bind().dialect.name == "sqlite":
                            # Prevent a concurrent HTTP write from invalidating
                            # the terminal transaction's read snapshot.
                            session.execute(text("BEGIN IMMEDIATE"))
                        repo = JobRepository(session, self._clock)
                        current = repo.get(row.owner_id, row.id)
                        if current:
                            if current.state == JobStatus.CANCEL_REQUESTED.value:
                                repo.finish_failure(
                                    current,
                                    "Cancellation committed before domain publication.",
                                    retryable=False,
                                )
                                self._audit(
                                    session,
                                    current,
                                    "cancelled",
                                    "cancel-requested",
                                    current.state,
                                )
                                session.commit()
                                self._log_transition(current, "cancelled")
                                continue
                            savepoint = session.begin_nested()
                            try:
                                applied_result = completion.apply(session)
                                savepoint.commit()
                            except JobPreparedFailure as exc:
                                savepoint.commit()
                                repo.finish_failure(current, str(exc))
                                self._audit(
                                    session,
                                    current,
                                    "failed",
                                    "running",
                                    current.state,
                                )
                                session.commit()
                                self._log_transition(
                                    current,
                                    "failed",
                                    diagnostic_classification="job-prepared-failure",
                                )
                                continue
                            except Exception:
                                savepoint.rollback()
                                raise
                            if applied_result is not None:
                                if applied_result.kind != row.kind:
                                    raise RuntimeError(
                                        "Applied job result kind does not match request kind."
                                    )
                                result = applied_result
                            repo.finish_success(
                                current,
                                result.result_ref,
                                result.result_hash,
                                warnings=result.warnings,
                                diagnostic_ref=result.diagnostic_ref,
                            )
                            self._audit(
                                session,
                                current,
                                "succeeded",
                                "running",
                                current.state,
                            )
                            session.commit()
                            self._log_transition(current, "succeeded")
                except Exception as exc:  # noqa: BLE001 -- rollback quarantines prepared output
                    with self._transition_lock, self._sessions() as session:
                        repo = JobRepository(session, self._clock)
                        current = repo.get(row.owner_id, row.id)
                        if current:
                            repo.finish_failure(
                                current,
                                f"{type(exc).__name__}: {exc}",
                            )
                            self._audit(
                                session, current, "failed", "running", current.state
                            )
                            session.commit()
                            self._log_transition(
                                current,
                                "failed",
                                diagnostic_classification="job-publication-failure",
                            )
            try:
                self._run_janitor()
            except Exception as exc:  # noqa: BLE001 -- janitor failure must not stop dispatch
                self._janitor_diagnostic = f"janitor failed: {type(exc).__name__}"
            if self._execute_external_cleanup is not None:
                try:
                    self._execute_external_cleanup(row.owner_id)
                except Exception:  # noqa: BLE001 -- durable intents remain retryable
                    self._janitor_diagnostic = "external cleanup failed"

    def _claim(self, lane: JobLane):
        with self._transition_lock, self._sessions() as session:
            repo = JobRepository(session, self._clock)
            cutoff = utc_text(
                self._clock.now() - timedelta(seconds=self._promotion_seconds())
            )
            row = repo.claim(lane, self._worker_id, cutoff)
            if row is None:
                return None
            pid = os.getpid()
            try:
                pgid = os.getpgid(pid)
            except OSError:
                pgid = None
            repo.add_attempt(
                row, process_identity=process_identity(pid), pid=pid, pgid=pgid
            )
            session.commit()
            self._log_transition(row, "started")
            session.expunge(row)
            return row

    def _is_cancel_requested(self, owner_id: str, job_id: str) -> bool:
        with self._sessions() as session:
            row = JobRepository(session, self._clock).get(owner_id, job_id)
            return row is None or row.state in ("cancel-requested", "cancelled")

    def _record_runtime(
        self,
        owner_id: str,
        job_id: str,
        *,
        pid: int | None = None,
        pgid: int | None = None,
        process_identity: str | None = None,
        temp_path: str | None = None,
    ) -> None:
        with self._transition_lock, self._sessions() as session:
            repo = JobRepository(session, self._clock)
            row = repo.get(owner_id, job_id)
            if row is None or row.state not in ("running", "cancel-requested"):
                raise JobCancelled("Job is no longer running.")
            repo.update_attempt_runtime(
                job_id,
                pid=pid,
                pgid=pgid,
                process_identity=process_identity,
                temp_path=temp_path,
            )
            session.commit()

    def _signal_running_attempt(self, job_id: str) -> None:
        with self._sessions() as session:
            attempt = JobRepository(session, self._clock).latest_attempt(job_id)
            if attempt is None or attempt.pid is None or attempt.pid == os.getpid():
                return
            if not _process_exists(attempt.pid):
                return
            identity = process_identity(attempt.pid)
            if "unavailable" in identity or identity != attempt.process_identity:
                return
            try:
                if attempt.pgid is not None:
                    os.killpg(attempt.pgid, signal.SIGTERM)
                else:
                    os.kill(attempt.pid, signal.SIGTERM)
            except ProcessLookupError:
                return

    def _audit(
        self, session: Session, row, action: str, before: str | None, after: str
    ) -> None:
        SqlAlchemyAuditRepository(session).append(
            AuditEvent(
                id=new_id(),
                owner_id=row.owner_id,
                goal_id=row.goal_id,
                actor_role="system-worker",
                entity_type="job",
                entity_id=row.id,
                action=action,
                before_hash=hash_payload(before) if before is not None else None,
                after_hash=hash_payload(after),
                reason=None,
                request_id=row.request_id,
                correlation_id=row.correlation_id,
                occurred_at=utc_text(self._clock.now()),
            )
        )

    @staticmethod
    def _log_transition(
        row,
        lifecycle: str,
        *,
        diagnostic_classification: str | None = None,
    ) -> None:
        log_event(
            f"job.{lifecycle}",
            request_id=row.request_id,
            correlation_id=row.correlation_id,
            owner_id=row.owner_id,
            goal_id=row.goal_id,
            job_id=row.id,
            run_id=row.run_id,
            lifecycle=lifecycle,
            diagnostic_classification=diagnostic_classification,
        )

    def _reconcile_attempt(self, repo: JobRepository, job_id: str) -> str | None:
        attempt = repo.latest_attempt(job_id)
        if attempt is None:
            return None
        diagnostics: list[str] = []
        if attempt.pid and attempt.pid != os.getpid() and _process_exists(attempt.pid):
            current_identity = process_identity(attempt.pid)
            if (
                "unavailable" in current_identity
                or current_identity != attempt.process_identity
            ):
                diagnostics.append(
                    "cleanup failed: recorded process identity could not be verified"
                )
            elif attempt.pgid is not None:
                try:
                    terminate_process_group(attempt.pgid)
                except OSError as exc:
                    diagnostics.append(f"cleanup failed: {type(exc).__name__}")
        if attempt.temp_path:
            failure = self._record_workspace_cleanup(repo, attempt)
            if failure:
                diagnostics.append(failure)
        return "; ".join(diagnostics) or None

    def _run_janitor(self) -> None:
        cutoff = utc_text(
            self._clock.now() - timedelta(seconds=self._retention_seconds())
        )
        with self._transition_lock, self._sessions() as session:
            repo = JobRepository(session, self._clock)
            for attempt in repo.cleanup_candidates(cutoff):
                if not attempt.temp_path:
                    continue
                failure = self._record_workspace_cleanup(repo, attempt)
                if failure:
                    row = repo.get(attempt.owner_id, attempt.job_id)
                    if row is not None:
                        row.diagnostic = failure
                        row.updated_at = utc_text(self._clock.now())
                        repo.add_event(row, "cleanup-failed")
            session.commit()

    def _record_workspace_cleanup(self, repo: JobRepository, attempt) -> str | None:
        """Persist a safe logical cleanup reference; never perform file I/O here."""
        raw_path = attempt.temp_path
        if raw_path is None:
            return None
        job = repo.get(attempt.owner_id, attempt.job_id)
        if job is None:
            attempt.temp_path = None
            return "cleanup failed: cleanup-owner-invalid"
        if self._record_cleanup is None:
            attempt.temp_path = None
            return "cleanup failed: cleanup-recorder-unavailable"
        failure = self._record_cleanup(
            repo.session, attempt.owner_id, job.goal_id, raw_path
        )
        attempt.temp_path = None
        return f"cleanup failed: {failure}" if failure is not None else None


def _retry_policy(kind: str) -> str:
    try:
        return _RETRY_POLICIES[kind]
    except KeyError as exc:
        raise ConflictError(
            f"Job kind {kind!r} has no registered retry policy."
        ) from exc


def _provider(value: int | Callable[[], int]) -> Callable[[], int]:
    return value if callable(value) else lambda: value


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

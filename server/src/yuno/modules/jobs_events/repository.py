from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from yuno.modules.data_lifecycle.models import (
    JobAttemptBodyRow,
    JobBodyRow,
    JobResultBodyRow,
)
from yuno.modules.jobs_events.models import (
    JobAttemptRow,
    JobEventRow,
    JobResultRow,
    JobRow,
)
from yuno.shared.application.jobs import (
    JobAttempt,
    JobLane,
    JobRef,
    JobRequest,
    JobStatus,
)
from yuno.shared.domain.clock import Clock, now_text
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

ACTIVE_STATES = ("queued", "running", "cancel-requested")
TERMINAL_STATES = ("succeeded", "failed", "cancelled")


class JobRepository:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock

    def find_active_dedupe(self, owner_id: str, kind: str, key: str) -> JobRow | None:
        return self.session.scalars(
            select(JobRow).where(
                JobRow.owner_id == owner_id,
                JobRow.kind == kind,
                JobRow.dedupe_key == key,
                JobRow.state.in_(ACTIVE_STATES),
            )
        ).first()

    def find_idempotency(self, owner_id: str, key: str) -> JobRow | None:
        return self.session.scalars(
            select(JobRow)
            .where(JobRow.owner_id == owner_id, JobRow.idempotency_key == key)
            .order_by(JobRow.queued_at, JobRow.id)
        ).first()

    def enqueue(self, request: JobRequest, lane: JobLane) -> JobRow:
        timestamp = now_text(self.clock)
        row = JobRow(
            id=request.requested_job_id or new_id(),
            owner_id=request.owner_id,
            goal_id=request.goal_id,
            kind=request.kind,
            schema_version=request.schema_version,
            lane=lane.value,
            state=JobStatus.QUEUED.value,
            retryable=0,
            dedupe_key=request.dedupe_key,
            idempotency_key=request.idempotency_key,
            payload_hash=hash_payload(request.payload),
            request_ref=request.request_ref,
            disclosure_ref=request.disclosure_ref,
            confirmation_ref=request.confirmation_ref,
            correlation_id=request.correlation_id,
            request_id=request.request_id,
            run_id=request.run_id,
            attempt=0,
            priority=100,
            queued_at=timestamp,
            updated_at=timestamp,
        )
        row.body = JobBodyRow(
            job_id=row.id,
            owner_id=row.owner_id,
            payload_json=json.dumps(
                dict(request.payload), sort_keys=True, separators=(",", ":")
            ),
            diagnostic=None,
        )
        self.session.add(row)
        self.session.flush()
        self.add_event(row, "enqueued")
        return row

    def get(self, owner_id: str, job_id: str) -> JobRow | None:
        return self.session.scalars(
            select(JobRow).where(JobRow.owner_id == owner_id, JobRow.id == job_id)
        ).one_or_none()

    def list(self, owner_id: str) -> Sequence[JobRow]:
        return tuple(
            self.session.scalars(
                select(JobRow)
                .where(JobRow.owner_id == owner_id)
                .order_by(JobRow.queued_at.desc(), JobRow.id.desc())
            ).all()
        )

    def list_events_after(
        self, owner_id: str, event_id: str | None
    ) -> Sequence[JobEventRow]:
        """Return retained owner events after an opaque cursor in stream order.

        An unknown cursor may have expired (or belong to another owner). Replaying
        every retained event is safe: clients deduplicate event ids and reconcile
        watched jobs through their authoritative GET endpoints after a loss.
        """
        after_event_id = "00000000000000000000"
        if event_id:
            after_event_id = (
                self.session.scalar(
                    select(JobEventRow.event_id).where(
                        JobEventRow.owner_id == owner_id,
                        JobEventRow.event_id == event_id,
                    )
                )
                or after_event_id
            )
        return tuple(
            self.session.scalars(
                select(JobEventRow)
                .where(
                    JobEventRow.owner_id == owner_id,
                    JobEventRow.event_id > after_event_id,
                )
                .order_by(JobEventRow.event_id)
            ).all()
        )

    def pending_count(self, owner_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(JobRow)
                .where(
                    JobRow.owner_id == owner_id,
                    JobRow.state.in_(("queued", "running")),
                )
            )
            or 0
        )

    def claim(
        self, lane: JobLane, worker_id: str, promoted_before: str
    ) -> JobRow | None:
        statement = select(JobRow).where(
            JobRow.lane == lane.value, JobRow.state == "queued"
        )
        if lane is JobLane.BACKGROUND:
            self.session.execute(
                update(JobRow)
                .where(
                    JobRow.lane == lane.value,
                    JobRow.state == "queued",
                    JobRow.queued_at <= promoted_before,
                    JobRow.priority > 0,
                )
                .values(priority=0)
            )
        candidate = self.session.scalars(
            statement.order_by(JobRow.priority, JobRow.queued_at, JobRow.id).limit(1)
        ).first()
        if candidate is None:
            return None
        timestamp = now_text(self.clock)
        attempt = candidate.attempt + 1
        changed = self.session.execute(
            update(JobRow)
            .where(JobRow.id == candidate.id, JobRow.state == "queued")
            .values(
                state="running",
                attempt=attempt,
                worker_id=worker_id,
                started_at=timestamp,
                updated_at=timestamp,
            )
        )
        if changed.rowcount != 1:
            return None
        candidate.state = "running"
        candidate.attempt = attempt
        candidate.worker_id = worker_id
        candidate.started_at = timestamp
        self.add_event(candidate, "claimed")
        return candidate

    def add_attempt(
        self, row: JobRow, *, process_identity: str, pid: int, pgid: int | None
    ) -> JobAttemptRow:
        attempt = JobAttemptRow(
            id=new_id(),
            owner_id=row.owner_id,
            job_id=row.id,
            attempt_number=row.attempt,
            substitution_ref=row.substitution_ref,
            confirmation_ref=row.confirmation_ref,
            started_at=row.started_at,
        )
        attempt.body = JobAttemptBodyRow(
            attempt_id=attempt.id,
            owner_id=attempt.owner_id,
            process_identity=process_identity,
            pid=pid,
            pgid=pgid,
            temp_path=None,
            diagnostic=None,
        )
        self.session.add(attempt)
        self.session.flush()
        return attempt

    def update_attempt_runtime(
        self,
        job_id: str,
        *,
        pid: int | None,
        pgid: int | None,
        process_identity: str | None,
        temp_path: str | None,
    ) -> None:
        attempt = self.latest_attempt(job_id)
        if attempt is None or attempt.ended_at is not None:
            raise RuntimeError("The active job attempt was not found.")
        if pid is not None:
            attempt.pid = pid
        if pgid is not None:
            attempt.pgid = pgid
        if process_identity is not None:
            attempt.process_identity = process_identity
        if temp_path is not None:
            attempt.temp_path = temp_path
        self.session.flush()

    def finish_success(
        self,
        row: JobRow,
        result_ref: str,
        result_hash: str,
        *,
        warnings: Sequence[str] = (),
        diagnostic_ref: str | None = None,
    ) -> str:
        current = self.get(row.owner_id, row.id)
        if current is None:
            return "missing"
        timestamp = now_text(self.clock)
        if current.state == "cancel-requested":
            self._finish_attempt(
                current,
                "cancelled",
                timestamp,
                "Cancellation committed before result; late result discarded.",
            )
            (
                current.state,
                current.retryable,
                current.terminal_at,
                current.updated_at,
            ) = "cancelled", 0, timestamp, timestamp
            self.add_event(current, "cancelled")
            return "cancelled"
        if current.state != "running":
            return current.state
        result = JobResultRow(
            id=new_id(),
            owner_id=current.owner_id,
            job_id=current.id,
            kind=current.kind,
            schema_version=current.schema_version,
            result_ref=result_ref,
            result_hash=result_hash,
            committed_at=timestamp,
        )
        result.body = JobResultBodyRow(
            result_id=result.id,
            owner_id=result.owner_id,
            warnings_json=json.dumps(tuple(warnings)),
            diagnostic_ref=diagnostic_ref,
        )
        self.session.add(result)
        current.state, current.retryable, current.terminal_at, current.updated_at = (
            "succeeded",
            0,
            timestamp,
            timestamp,
        )
        current.result_ref, current.result_hash = result_ref, result_hash
        self._finish_attempt(current, "succeeded", timestamp, None)
        self.add_event(current, "result-committed", result_ref=result_ref)
        self.session.flush()
        return "succeeded"

    def finish_failure(
        self, row: JobRow, diagnostic: str, *, retryable: bool = True
    ) -> None:
        current = self.get(row.owner_id, row.id)
        if current is None or current.state not in ("running", "cancel-requested"):
            return
        timestamp = now_text(self.clock)
        state = "cancelled" if current.state == "cancel-requested" else "failed"
        current.state, current.retryable = state, int(retryable and state == "failed")
        current.diagnostic, current.terminal_at, current.updated_at = (
            diagnostic,
            timestamp,
            timestamp,
        )
        self._finish_attempt(current, state, timestamp, diagnostic)
        self.add_event(current, state)

    def cancel(self, row: JobRow) -> JobRow:
        if row.state in TERMINAL_STATES or row.state == "cancel-requested":
            return row
        timestamp = now_text(self.clock)
        if row.state == "queued":
            row.state, row.terminal_at = "cancelled", timestamp
            row.retryable = 0
            self.add_event(row, "cancelled")
        else:
            row.state = "cancel-requested"
            self.add_event(row, "cancel-requested")
        row.updated_at = timestamp
        return row

    def committed_result_for_dedupe(self, row: JobRow) -> JobRow | None:
        if row.dedupe_key is None:
            return None
        return self.session.scalars(
            select(JobRow)
            .join(JobResultRow, JobResultRow.job_id == JobRow.id)
            .where(
                JobRow.owner_id == row.owner_id,
                JobRow.kind == row.kind,
                JobRow.dedupe_key == row.dedupe_key,
                JobRow.state == "succeeded",
            )
            .order_by(JobRow.terminal_at.desc())
        ).first()

    def adopt_committed_result(self, row: JobRow, source: JobRow) -> None:
        source_result = self.session.scalars(
            select(JobResultRow).where(JobResultRow.job_id == source.id)
        ).one()
        timestamp = now_text(self.clock)
        adopted = JobResultRow(
            id=new_id(),
            owner_id=row.owner_id,
            job_id=row.id,
            kind=source_result.kind,
            schema_version=source_result.schema_version,
            result_ref=source_result.result_ref,
            result_hash=source_result.result_hash,
            committed_at=timestamp,
        )
        adopted.body = JobResultBodyRow(
            result_id=adopted.id,
            owner_id=adopted.owner_id,
            warnings_json=source_result.warnings_json,
            diagnostic_ref=source_result.diagnostic_ref,
        )
        self.session.add(adopted)
        row.state, row.retryable = "succeeded", 0
        row.result_ref, row.result_hash = (
            source_result.result_ref,
            source_result.result_hash,
        )
        row.diagnostic, row.terminal_at, row.updated_at = None, timestamp, timestamp
        self.add_event(row, "cache-short-circuit", result_ref=row.result_ref)
        self.session.flush()

    def requeue(
        self,
        row: JobRow,
        *,
        substitution_ref: str | None,
        confirmation_ref: str | None,
        event_type: str,
    ) -> None:
        timestamp = now_text(self.clock)
        row.state, row.retryable, row.diagnostic, row.terminal_at = (
            "queued",
            0,
            None,
            None,
        )
        row.substitution_ref, row.confirmation_ref = substitution_ref, confirmation_ref
        row.queued_at, row.updated_at = timestamp, timestamp
        row.priority = 100
        self.add_event(row, event_type)

    def startup_rows(self) -> Sequence[JobRow]:
        return tuple(
            self.session.scalars(
                select(JobRow).where(JobRow.state.in_(("running", "cancel-requested")))
            ).all()
        )

    def latest_attempt(self, job_id: str) -> JobAttemptRow | None:
        return self.session.scalars(
            select(JobAttemptRow)
            .where(JobAttemptRow.job_id == job_id)
            .order_by(JobAttemptRow.attempt_number.desc())
        ).first()

    def list_attempts(self, owner_id: str, job_id: str) -> Sequence[JobAttemptRow]:
        return tuple(
            self.session.scalars(
                select(JobAttemptRow)
                .where(
                    JobAttemptRow.owner_id == owner_id,
                    JobAttemptRow.job_id == job_id,
                )
                .order_by(JobAttemptRow.attempt_number)
            ).all()
        )

    def cleanup_candidates(self, ended_before: str) -> Sequence[JobAttemptRow]:
        return tuple(
            self.session.scalars(
                select(JobAttemptRow)
                .join(JobRow, JobRow.id == JobAttemptRow.job_id)
                .join(
                    JobAttemptBodyRow,
                    JobAttemptBodyRow.attempt_id == JobAttemptRow.id,
                )
                .where(
                    JobRow.state.in_(TERMINAL_STATES),
                    JobAttemptBodyRow.temp_path.is_not(None),
                    JobAttemptRow.ended_at.is_not(None),
                    JobAttemptRow.ended_at <= ended_before,
                )
            ).all()
        )

    def reconcile_row(self, row: JobRow, diagnostic: str | None = None) -> None:
        timestamp = now_text(self.clock)
        if row.state == "cancel-requested":
            row.state, row.retryable = "cancelled", 0
            outcome = "cancelled"
        else:
            row.state, row.retryable = "failed", 1
            outcome = "failed"
        row.diagnostic = (
            diagnostic or "Worker stopped before the attempt reached a terminal commit."
        )
        row.terminal_at, row.updated_at = timestamp, timestamp
        self._finish_attempt(row, outcome, timestamp, row.diagnostic)
        self.add_event(row, "startup-reconciled")

    def add_event(
        self, row: JobRow, event_type: str, *, result_ref: str | None = None
    ) -> None:
        self.session.add(
            JobEventRow(
                owner_id=row.owner_id,
                job_id=row.id,
                goal_id=row.goal_id,
                run_id=row.run_id,
                type=event_type,
                state=row.state,
                result_ref=result_ref,
                retryable=row.retryable,
                correlation_id=row.correlation_id,
                request_id=row.request_id,
                created_at=now_text(self.clock),
            )
        )

    def _finish_attempt(
        self, row: JobRow, outcome: str, timestamp: str, diagnostic: str | None
    ) -> None:
        attempt = self.latest_attempt(row.id)
        if attempt is not None and attempt.ended_at is None:
            attempt.ended_at, attempt.outcome, attempt.diagnostic = (
                timestamp,
                outcome,
                diagnostic,
            )


def as_ref(row: JobRow, *, deduplicated: bool = False) -> JobRef:
    return JobRef(
        job_id=row.id,
        kind=row.kind,
        status=JobStatus(row.state),
        enqueued_at=row.queued_at,
        deduplicated=deduplicated,
        lane=JobLane(row.lane),
        retryable=bool(row.retryable),
        goal_id=row.goal_id,
        schema_version=row.schema_version,
        attempt=row.attempt,
        diagnostic=row.diagnostic,
        started_at=row.started_at,
        terminal_at=row.terminal_at,
        substitution_ref=row.substitution_ref,
        result_ref=row.result_ref,
        result_hash=row.result_hash,
    )


def as_attempt(row: JobAttemptRow) -> JobAttempt:
    return JobAttempt(
        row.attempt_number,
        row.process_identity,
        row.pid,
        row.pgid,
        row.temp_path,
        row.started_at,
        row.ended_at,
        row.outcome,
        row.diagnostic,
        row.substitution_ref,
        row.confirmation_ref,
    )

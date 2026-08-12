"""IDK-401 crash, lane, dedupe, cancellation, atomicity and retry contract."""

from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import func, select, text

from tests.job_assertions import wait_for_job
from yuno.modules.audit.models import AuditEventRow
from yuno.modules.identity.service import ensure_local_owner
from yuno.modules.jobs_events import service as job_service
from yuno.modules.jobs_events.models import (
    JobAttemptRow,
    JobEventRow,
    JobResultRow,
    JobRow,
)
from yuno.modules.jobs_events.repository import JobRepository
from yuno.modules.jobs_events.service import DurableJobDispatcher
from yuno.shared.application.jobs import (
    JobCompletion,
    JobExecution,
    JobLane,
    JobRef,
    JobRequest,
    JobResult,
    JobStatus,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import ConflictError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def _owner(uow_factory) -> str:
    with uow_factory() as uow:
        owner = ensure_local_owner(uow, "Job test owner")
        uow.commit()
        return owner.id


def _dispatcher(session_factory, handlers: dict[str, object]) -> DurableJobDispatcher:
    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=20,
        background_age_promotion_seconds=1,
        janitor_retention_seconds=1,
    )
    for kind, handler in handlers.items():

        def typed(execution: JobExecution, operation=handler, result_kind=kind):
            operation(execution.request)
            result_ref = f"test:{execution.request.requested_job_id}"
            return JobCompletion(
                JobResult(result_kind, "1", result_ref, hash_payload(result_ref)),
                lambda _session: None,
            )

        dispatcher.register(kind, typed)
    dispatcher.start()
    return dispatcher


def _wait(
    dispatcher: DurableJobDispatcher,
    owner_id: str,
    job_id: str,
    state: JobStatus,
) -> JobRef:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        ref = dispatcher.get(owner_id, job_id)
        if ref is not None and ref.status is state:
            return ref
        time.sleep(0.01)
    pytest.fail(
        f"job {job_id} did not reach {state.value}; "
        f"current={dispatcher.get(owner_id, job_id)}; "
        f"lane diagnostics={dispatcher.lane_diagnostics}"
    )


def test_reserved_interactive_lane_is_not_starved_by_background(
    session_factory, uow_factory
) -> None:
    owner = _owner(uow_factory)
    background_started, release = threading.Event(), threading.Event()

    def background(_request):
        background_started.set()
        assert release.wait(5)

    dispatcher = _dispatcher(
        session_factory,
        {"bulk_index": background, "evaluate_practice_answer": lambda _request: None},
    )
    background_ref = dispatcher.enqueue(JobRequest("bulk_index", owner, {}))
    try:
        assert background_started.wait(5)
        interactive = dispatcher.enqueue(
            JobRequest("evaluate_practice_answer", owner, {})
        )
        assert interactive.status is JobStatus.QUEUED
        _wait(dispatcher, owner, interactive.job_id, JobStatus.SUCCEEDED)
        assert interactive.lane is JobLane.INTERACTIVE
        assert dispatcher.get(owner, background_ref.job_id).status is JobStatus.RUNNING
    finally:
        release.set()
        _wait(dispatcher, owner, background_ref.job_id, JobStatus.SUCCEEDED)
        dispatcher.stop()


def test_active_dedupe_and_terminal_commit_are_persisted(
    session_factory, uow_factory
) -> None:
    owner = _owner(uow_factory)
    started, release = threading.Event(), threading.Event()
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(5)

    dispatcher = _dispatcher(session_factory, {"bulk_index": handler})
    first = dispatcher.enqueue(JobRequest("bulk_index", owner, {}, dedupe_key="same"))
    try:
        assert started.wait(5)
        duplicate = dispatcher.enqueue(
            JobRequest("bulk_index", owner, {}, dedupe_key="same")
        )
        assert duplicate.deduplicated and calls == 1
    finally:
        release.set()
        _wait(dispatcher, owner, first.job_id, JobStatus.SUCCEEDED)
        dispatcher.stop()
    with session_factory() as session:
        job = session.get(JobRow, first.job_id)
        assert job is not None and job.state == "succeeded"
        assert (
            session.scalar(
                select(func.count())
                .select_from(JobResultRow)
                .where(JobResultRow.job_id == job.id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(JobEventRow)
                .where(JobEventRow.job_id == job.id, JobEventRow.state == "succeeded")
            )
            == 1
        )


def test_cancel_race_obeys_commit_order(session_factory, uow_factory) -> None:
    owner = _owner(uow_factory)
    started, release = threading.Event(), threading.Event()

    def handler(_request):
        started.set()
        assert release.wait(5)

    dispatcher = _dispatcher(session_factory, {"bulk_index": handler})
    dispatcher.enqueue(JobRequest("bulk_index", owner, {}))
    assert started.wait(5)
    with session_factory() as session:
        job_id = session.scalar(
            select(JobRow.id).where(JobRow.owner_id == owner, JobRow.state == "running")
        )
    assert dispatcher.cancel(owner, job_id).status is JobStatus.CANCEL_REQUESTED
    release.set()
    _wait(dispatcher, owner, job_id, JobStatus.CANCELLED)
    with session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(JobResultRow)
                .where(JobResultRow.job_id == job_id)
            )
            == 0
        )
    completed = dispatcher.enqueue(JobRequest("bulk_index", owner, {}))
    _wait(dispatcher, owner, completed.job_id, JobStatus.SUCCEEDED)
    assert dispatcher.cancel(owner, completed.job_id).status is JobStatus.SUCCEEDED
    dispatcher.stop()


def test_startup_reconciles_active_states_and_sweeps_temp_path(
    session_factory, uow_factory, tmp_path
) -> None:
    owner = _owner(uow_factory)
    clock = SystemClock()
    timestamp = now_text(clock)
    temp = tmp_path / "attempt"
    temp.mkdir()
    (temp / "partial").write_text("x")
    with session_factory() as session:
        repo = JobRepository(session, clock)
        running = repo.enqueue(JobRequest("bulk_index", owner, {}), JobLane.BACKGROUND)
        queued = repo.enqueue(JobRequest("bulk_index", owner, {}), JobLane.BACKGROUND)
        cancelling = repo.enqueue(
            JobRequest("bulk_index", owner, {}), JobLane.BACKGROUND
        )
        running.state = "running"
        running.attempt = 1
        running.started_at = timestamp
        cancelling.state = "cancel-requested"
        session.add(
            JobAttemptRow(
                id=new_id(),
                owner_id=owner,
                job_id=running.id,
                attempt_number=1,
                process_identity="999:old",
                pid=999,
                pgid=999,
                temp_path=str(temp),
                started_at=timestamp,
            )
        )
        session.commit()
        ids = running.id, queued.id, cancelling.id
    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=20,
        background_age_promotion_seconds=1,
        janitor_retention_seconds=1,
    )
    dispatcher.register("bulk_index", lambda _request: None)
    dispatcher.reconcile_startup()
    assert dispatcher.get(owner, ids[0]).status is JobStatus.FAILED
    assert dispatcher.get(owner, ids[0]).retryable is True
    assert dispatcher.get(owner, ids[1]).status is JobStatus.QUEUED
    assert dispatcher.get(owner, ids[2]).status is JobStatus.CANCELLED
    assert not temp.exists()


def test_retry_strategies_are_behaviorally_distinct(
    session_factory, uow_factory
) -> None:
    owner = _owner(uow_factory)
    failing = lambda _request: (_ for _ in ()).throw(RuntimeError("failed"))
    dispatcher = _dispatcher(
        session_factory,
        {
            "rebuild_index": failing,
            "generate_topic_content": failing,
            "generate_mock_next_turn": failing,
            "java_runner": failing,
        },
    )
    index = dispatcher.enqueue(JobRequest("rebuild_index", owner, {}))
    _wait(dispatcher, owner, index.job_id, JobStatus.FAILED)
    assert dispatcher.retry(owner, index.job_id).status is JobStatus.QUEUED
    _wait(dispatcher, owner, index.job_id, JobStatus.FAILED)
    interview = dispatcher.enqueue(JobRequest("generate_mock_next_turn", owner, {}))
    _wait(dispatcher, owner, interview.job_id, JobStatus.FAILED)
    with pytest.raises(ConflictError, match="substitution"):
        dispatcher.retry(owner, interview.job_id)
    resumed = dispatcher.retry(
        owner, interview.job_id, substitution_ref="turn:replacement"
    )
    assert resumed.status is JobStatus.QUEUED
    _wait(dispatcher, owner, interview.job_id, JobStatus.FAILED)
    interview_attempts = dispatcher.attempts(owner, interview.job_id)
    assert interview_attempts[-1].substitution_ref == "turn:replacement"
    runner = dispatcher.enqueue(JobRequest("java_runner", owner, {}))
    _wait(dispatcher, owner, runner.job_id, JobStatus.FAILED)
    with pytest.raises(ConflictError, match="confirmation"):
        dispatcher.retry(owner, runner.job_id)
    fresh = dispatcher.retry(
        owner, runner.job_id, confirmation_ref="confirmation:fresh"
    )
    assert fresh.status is JobStatus.QUEUED
    _wait(dispatcher, owner, runner.job_id, JobStatus.FAILED)
    runner_attempts = dispatcher.attempts(owner, runner.job_id)
    assert runner_attempts[-1].confirmation_ref == "confirmation:fresh"
    dispatcher.register(
        "generate_topic_content",
        lambda execution: JobCompletion(
            JobResult(
                "generate_topic_content",
                "1",
                f"test:{execution.request.requested_job_id}",
                hash_payload(execution.request.payload),
            ),
            lambda _session: None,
        ),
    )
    cached = dispatcher.enqueue(
        JobRequest("generate_topic_content", owner, {}, dedupe_key="cache-key")
    )
    cached = _wait(dispatcher, owner, cached.job_id, JobStatus.SUCCEEDED)
    dispatcher.register("generate_topic_content", failing)
    generation = dispatcher.enqueue(
        JobRequest("generate_topic_content", owner, {}, dedupe_key="cache-key")
    )
    _wait(dispatcher, owner, generation.job_id, JobStatus.FAILED)
    cache_hit = dispatcher.retry(owner, generation.job_id)
    assert cache_hit.status is JobStatus.SUCCEEDED
    assert cache_hit.job_id == generation.job_id
    assert cache_hit.result_ref == cached.result_ref
    assert cache_hit.deduplicated is True
    dispatcher.stop()


def test_owner_scoped_jobs_api_exposes_configuration_and_authoritative_state(
    client, uow_factory
) -> None:
    owner = _owner(uow_factory)
    queued = client.app.state.dispatcher.enqueue(
        JobRequest("generate_topic_content", owner, {"attempt_id": "missing"})
    )
    assert queued.status is JobStatus.QUEUED
    terminal = wait_for_job(client, queued.job_id, "failed")
    assert terminal["retryable"] is True

    listing = client.get("/api/v1/jobs")
    assert listing.status_code == 200
    assert listing.json()["pending_job_cap"] == 100
    assert {job["job_id"] for job in listing.json()["jobs"]} == {queued.job_id}
    repeated_cancel = client.post(f"/api/v1/jobs/{queued.job_id}/cancel")
    assert repeated_cancel.status_code == 200
    assert repeated_cancel.json()["status"] == "failed"
    assert client.get("/api/v1/jobs/not-owned-or-missing").status_code == 404


def test_queued_cancel_and_pending_cap_are_durable(
    session_factory, uow_factory
) -> None:
    owner = _owner(uow_factory)
    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=lambda: 1,
        background_age_promotion_seconds=lambda: 60,
        janitor_retention_seconds=lambda: 60,
    )
    dispatcher.register(
        "rebuild_index",
        lambda execution: JobCompletion(
            JobResult("rebuild_index", "1", "index:1", hash_payload("index:1")),
            lambda _session: None,
        ),
    )
    queued = dispatcher.enqueue(JobRequest("rebuild_index", owner, {}))
    with pytest.raises(Exception, match="pending-job cap"):
        dispatcher.enqueue(JobRequest("rebuild_index", owner, {}))
    cancelled = dispatcher.cancel(owner, queued.job_id)
    assert cancelled.status is JobStatus.CANCELLED
    assert dispatcher.cancel(owner, queued.job_id).status is JobStatus.CANCELLED


def test_attempt_runtime_result_and_audit_are_persisted(
    session_factory, uow_factory, tmp_path
) -> None:
    owner = _owner(uow_factory)
    runtime_path = tmp_path / "runtime"
    runtime_path.mkdir()

    def handler(execution: JobExecution) -> JobCompletion:
        execution.record_runtime(temp_path=str(runtime_path))
        return JobCompletion(
            JobResult(
                "rebuild_index",
                "7",
                "index:authoritative",
                hash_payload("authoritative"),
            ),
            lambda _session: None,
        )

    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=10,
        background_age_promotion_seconds=60,
        janitor_retention_seconds=0,
    )
    dispatcher.register("rebuild_index", handler)
    dispatcher.start()
    ref = dispatcher.enqueue(JobRequest("rebuild_index", owner, {}))
    terminal = _wait(dispatcher, owner, ref.job_id, JobStatus.SUCCEEDED)
    assert terminal.result_ref == "index:authoritative"
    attempts = dispatcher.attempts(owner, ref.job_id)
    assert attempts[0].temp_path == str(runtime_path)
    with session_factory() as session:
        audit_actions = session.scalars(
            select(AuditEventRow.action).where(AuditEventRow.entity_id == ref.job_id)
        ).all()
    assert {"enqueued", "succeeded"} <= set(audit_actions)
    dispatcher.stop()
    assert not runtime_path.exists()


def test_only_one_worker_process_owner_per_database(session_factory) -> None:
    first = DurableJobDispatcher(
        session_factory,
        pending_cap=10,
        background_age_promotion_seconds=60,
        janitor_retention_seconds=60,
    )
    second = DurableJobDispatcher(
        session_factory,
        pending_cap=10,
        background_age_promotion_seconds=60,
        janitor_retention_seconds=60,
    )
    first.start()
    try:
        with pytest.raises(RuntimeError, match="Another durable worker process"):
            second.start()
    finally:
        first.stop()


def test_apply_failure_rolls_back_domain_output_and_keeps_lane_alive(
    session_factory, uow_factory
) -> None:
    owner = _owner(uow_factory)
    with session_factory.begin() as session:
        session.execute(text("CREATE TABLE completion_probe (id TEXT PRIMARY KEY)"))

    def broken(_execution: JobExecution) -> JobCompletion:
        def apply(session) -> None:
            session.execute(
                text("INSERT INTO completion_probe (id) VALUES ('must-rollback')")
            )
            raise RuntimeError("crash before shared commit")

        return JobCompletion(
            JobResult("rebuild_index", "1", "probe:must-rollback", hash_payload("x")),
            apply,
        )

    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=10,
        background_age_promotion_seconds=60,
        janitor_retention_seconds=60,
    )
    dispatcher.register("rebuild_index", broken)
    dispatcher.start()
    ref = dispatcher.enqueue(JobRequest("rebuild_index", owner, {}))
    _wait(dispatcher, owner, ref.job_id, JobStatus.FAILED)
    with session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM completion_probe")) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(JobResultRow)
                .where(JobResultRow.job_id == ref.job_id)
            )
            == 0
        )
    dispatcher.stop()


def test_terminal_transaction_serializes_concurrent_http_writes(
    session_factory, uow_factory
) -> None:
    owner = _owner(uow_factory)
    with session_factory.begin() as session:
        session.execute(text("CREATE TABLE completion_lock_probe (id TEXT PRIMARY KEY)"))

    apply_started = threading.Event()
    release_apply = threading.Event()
    writer_started = threading.Event()
    writer_done = threading.Event()
    writer_errors: list[Exception] = []

    def handler(_execution: JobExecution) -> JobCompletion:
        def apply(session) -> None:
            apply_started.set()
            assert release_apply.wait(5)
            session.execute(
                text("INSERT INTO completion_lock_probe (id) VALUES ('job')")
            )

        return JobCompletion(
            JobResult("rebuild_index", "1", "probe:job", hash_payload("job")),
            apply,
        )

    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=10,
        background_age_promotion_seconds=60,
        janitor_retention_seconds=60,
    )
    dispatcher.register("rebuild_index", handler)
    dispatcher.start()
    ref = dispatcher.enqueue(JobRequest("rebuild_index", owner, {}))
    assert apply_started.wait(5)

    def write_concurrently() -> None:
        try:
            writer_started.set()
            with session_factory.begin() as session:
                session.execute(
                    text("INSERT INTO completion_lock_probe (id) VALUES ('http')")
                )
        except Exception as exc:  # noqa: BLE001 -- collected for the assertion thread
            writer_errors.append(exc)
        finally:
            writer_done.set()

    writer = threading.Thread(target=write_concurrently)
    writer.start()
    assert writer_started.wait(5)
    time.sleep(0.05)
    assert not writer_done.is_set()
    release_apply.set()
    _wait(dispatcher, owner, ref.job_id, JobStatus.SUCCEEDED)
    writer.join(5)
    assert not writer.is_alive()
    assert writer_errors == []
    with session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM completion_lock_probe")) == 2
    dispatcher.stop()


def test_background_age_promotion_and_fifo(session_factory, uow_factory) -> None:
    owner = _owner(uow_factory)
    clock = SystemClock()
    with session_factory() as session:
        repo = JobRepository(session, clock)
        old = repo.enqueue(JobRequest("rebuild_index", owner, {}), JobLane.BACKGROUND)
        old.queued_at = "2000-01-01T00:00:00.000000Z"
        newer = repo.enqueue(JobRequest("rebuild_index", owner, {}), JobLane.BACKGROUND)
        newer.priority = 10
        session.commit()
    with session_factory() as session:
        claimed = JobRepository(session, clock).claim(
            JobLane.BACKGROUND, "worker:test", "2020-01-01T00:00:00.000000Z"
        )
        assert claimed is not None and claimed.id == old.id
        session.rollback()
    with session_factory() as session:
        repo = JobRepository(session, clock)
        first = repo.enqueue(
            JobRequest("rebuild_index", owner, {}), JobLane.INTERACTIVE
        )
        second = repo.enqueue(
            JobRequest("rebuild_index", owner, {}), JobLane.INTERACTIVE
        )
        first.queued_at = second.queued_at = "2026-01-01T00:00:00.000000Z"
        session.commit()
        claimed = repo.claim(
            JobLane.INTERACTIVE, "worker:test", "2000-01-01T00:00:00.000000Z"
        )
        assert claimed is not None and claimed.id == min(first.id, second.id)


def test_startup_cleanup_failure_aborts_and_rolls_back(
    session_factory, uow_factory, monkeypatch
) -> None:
    owner = _owner(uow_factory)
    clock = SystemClock()
    timestamp = now_text(clock)
    with session_factory() as session:
        repo = JobRepository(session, clock)
        row = repo.enqueue(JobRequest("rebuild_index", owner, {}), JobLane.BACKGROUND)
        row.state, row.attempt, row.started_at = "running", 1, timestamp
        repo.add_attempt(row, process_identity="999:old", pid=999, pgid=999)
        repo.latest_attempt(row.id).temp_path = "/tmp/yuno-unremovable-test"
        session.commit()
    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=10,
        background_age_promotion_seconds=60,
        janitor_retention_seconds=60,
    )
    monkeypatch.setattr(
        dispatcher, "_remove_temp_path", lambda _path: "cleanup failed: PermissionError"
    )
    with pytest.raises(RuntimeError, match="Startup reconciliation failed"):
        dispatcher.start()
    assert dispatcher.get(owner, row.id).status is JobStatus.RUNNING


def test_pid_identity_mismatch_refuses_signal_and_owned_reconcile(
    session_factory, uow_factory, monkeypatch
) -> None:
    owner = _owner(uow_factory)
    dispatcher = DurableJobDispatcher(
        session_factory,
        pending_cap=10,
        background_age_promotion_seconds=60,
        janitor_retention_seconds=60,
    )
    clock = SystemClock()
    with session_factory() as session:
        repo = JobRepository(session, clock)
        row = repo.enqueue(JobRequest("rebuild_index", owner, {}), JobLane.BACKGROUND)
        row.state, row.attempt, row.started_at, row.worker_id = (
            "running",
            1,
            now_text(clock),
            dispatcher._worker_id,  # noqa: SLF001
        )
        repo.add_attempt(
            row, process_identity="424242:original", pid=424242, pgid=424242
        )
        session.commit()
    killed = []
    monkeypatch.setattr(job_service, "_process_exists", lambda _pid: True)
    monkeypatch.setattr(job_service, "process_identity", lambda _pid: "424242:reused")
    monkeypatch.setattr(job_service.os, "killpg", lambda *args: killed.append(args))
    dispatcher._signal_running_attempt(row.id)  # noqa: SLF001
    assert killed == []
    with pytest.raises(ConflictError, match="still owns"):
        dispatcher.reconcile(owner, row.id)

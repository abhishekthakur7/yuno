from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from yuno.modules.data_lifecycle.domain import (
    CleanupIntent,
    CleanupIntentKind,
    CleanupIntentStatus,
)
from yuno.modules.data_lifecycle.service import (
    ApprovedCleanupRoots,
    RetentionPolicy,
    execute_pending_cleanup,
    run_retention_cycle,
    runner_workspace_path_ref,
)
from yuno.shared.domain.hashing import hash_payload


class FakeRepository:
    def __init__(self, intent: CleanupIntent | None = None) -> None:
        self.intent = intent
        self.calls: list[tuple] = []

    def expire_diagnostics(self, *args):
        self.calls.append(("diagnostics", *args))
        return 1

    def expire_interviews(self, *args):
        self.calls.append(("interviews", *args))
        return 2

    def purge_job_exhaust(self, *args):
        self.calls.append(("jobs", *args))
        return 3

    def expire_job_events(self, *args):
        self.calls.append(("events", *args))
        return 4

    def expire_runner_outputs(self, *args):
        self.calls.append(("runner", *args))
        return 5

    def expire_export_packages(self, *args):
        self.calls.append(("packages", *args))
        return 6

    def expire_export_operations(self, *args):
        self.calls.append(("operations", *args))
        return 7

    def list_pending_cleanup_intents(self, owner_id):
        self.calls.append(("list", owner_id))
        return (self.intent,) if self.intent else ()

    def add_cleanup_intent(self, intent):
        self.calls.append(("add", intent))
        self.intent = intent

    def finish_cleanup_intent(self, *args):
        self.calls.append(("finish", *args))
        return True

    def fail_cleanup_intent(self, *args):
        self.calls.append(("fail", *args))
        return True


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository, state: dict[str, bool]) -> None:
        self.data_lifecycle = repository
        self.state = state

    def __enter__(self):
        assert not self.state["active"]
        self.state["active"] = True
        return self

    def __exit__(self, *_args):
        self.state["active"] = False

    def commit(self):
        self.data_lifecycle.calls.append(("commit",))


def _factory(repository: FakeRepository):
    state = {"active": False}

    def factory():
        return FakeUnitOfWork(repository, state)

    return factory, state


def _intent(kind: CleanupIntentKind, path_ref: str) -> CleanupIntent:
    return CleanupIntent(
        "intent-1",
        "owner-1",
        None,
        kind,
        path_ref,
        hash_payload(path_ref),
        CleanupIntentStatus.PENDING,
        None,
        0,
        "2026-01-01T00:00:00.000000Z",
        "2026-01-01T00:00:00.000000Z",
        None,
    )


def test_retention_cycle_uses_policy_cutoffs_and_exact_export_expiry(
    tmp_path: Path,
) -> None:
    repository = FakeRepository()
    factory, _state = _factory(repository)
    now = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    retained, cleaned = run_retention_cycle(
        factory,
        "owner-1",
        now=now,
        roots=ApprovedCleanupRoots(tmp_path, tmp_path),
        policy=RetentionPolicy(),
    )

    assert retained.jobs == 3
    assert cleaned.completed == cleaned.failed == 0
    assert (
        "diagnostics",
        "owner-1",
        "2026-07-14T12:00:00.000000Z",
        "2026-08-13T12:00:00.000000Z",
    ) in repository.calls
    assert ("interviews", "owner-1", "2026-07-14T12:00:00.000000Z") in repository.calls
    assert ("jobs", "owner-1", "2026-07-14T12:00:00.000000Z") in repository.calls
    assert (
        "events",
        "owner-1",
        "2026-08-06T12:00:00.000000Z",
        10_000,
    ) in repository.calls
    assert ("runner", "owner-1", "2026-08-06T12:00:00.000000Z") in repository.calls
    assert ("packages", "owner-1", "2026-08-13T12:00:00.000000Z") in repository.calls
    assert ("operations", "owner-1", "2026-08-13T12:00:00.000000Z") in repository.calls


def test_external_cleanup_runs_outside_uow_and_marks_completion(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    digest = "a" * 64
    (source / digest).write_text("sensitive")
    repository = FakeRepository(
        _intent(CleanupIntentKind.SOURCE_SNAPSHOT, f"source-snapshot:{digest}")
    )
    factory, state = _factory(repository)

    result = execute_pending_cleanup(
        factory,
        "owner-1",
        roots=ApprovedCleanupRoots(tmp_path / "runner", source),
        completed_at="2026-08-13T12:00:00.000000Z",
    )

    assert not state["active"]
    assert not (source / digest).exists()
    assert result.completed == 1
    assert (
        "finish",
        "owner-1",
        "intent-1",
        "2026-08-13T12:00:00.000000Z",
    ) in repository.calls


def test_external_cleanup_rejects_reference_outside_approved_root(
    tmp_path: Path,
) -> None:
    repository = FakeRepository(
        _intent(CleanupIntentKind.SOURCE_SNAPSHOT, "source-snapshot:../outside")
    )
    factory, _state = _factory(repository)

    result = execute_pending_cleanup(
        factory,
        "owner-1",
        roots=ApprovedCleanupRoots(tmp_path / "runner", tmp_path / "source"),
        completed_at="2026-08-13T12:00:00.000000Z",
    )

    assert result.failed == 1
    failure = next(call for call in repository.calls if call[0] == "fail")
    assert failure[3] == "cleanup-reference-invalid"


def test_provider_quarantine_cleanup_removes_only_hashed_file_in_approved_root(
    tmp_path: Path,
) -> None:
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    digest = "b" * 64
    output = quarantine / digest
    output.write_text("quarantined-sensitive-output")
    repository = FakeRepository(
        _intent(
            CleanupIntentKind.PROVIDER_QUARANTINE,
            f"secure-provider-output:{digest}",
        )
    )
    factory, state = _factory(repository)

    result = execute_pending_cleanup(
        factory,
        "owner-1",
        roots=ApprovedCleanupRoots(
            tmp_path / "runner", tmp_path / "source", quarantine
        ),
        completed_at="2026-08-13T12:00:00.000000Z",
    )

    assert not state["active"]
    assert not output.exists()
    assert result.completed == 1


def test_external_cleanup_rejects_tampered_reference_hash(tmp_path: Path) -> None:
    digest = "c" * 64
    intent = _intent(CleanupIntentKind.SOURCE_SNAPSHOT, f"source-snapshot:{digest}")
    repository = FakeRepository(
        CleanupIntent(**{**intent.__dict__, "path_hash": "0" * 64})
    )
    factory, _state = _factory(repository)

    result = execute_pending_cleanup(
        factory,
        "owner-1",
        roots=ApprovedCleanupRoots(tmp_path / "runner", tmp_path / "source"),
        completed_at="2026-08-13T12:00:00.000000Z",
    )

    assert result.failed == 1
    failure = next(call for call in repository.calls if call[0] == "fail")
    assert failure[3] == "cleanup-reference-hash-mismatch"


def test_runner_workspace_reference_rejects_absolute_escape_and_traversal(
    tmp_path: Path,
) -> None:
    runner = tmp_path / "runner"

    assert (
        runner_workspace_path_ref(runner / "yuno-runner-safe", runner)
        == "runner-workspace:yuno-runner-safe"
    )
    assert runner_workspace_path_ref("/etc/yuno-runner-safe", runner) is None
    assert (
        runner_workspace_path_ref(runner / "nested" / ".." / "yuno-runner-safe", runner)
        is None
    )
    assert runner_workspace_path_ref(runner / "not-a-runner", runner) is None


def test_runner_workspace_cleanup_rejects_symlink_then_retries_safely(
    tmp_path: Path,
) -> None:
    runner = tmp_path / "runner"
    runner.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sensitive").write_text("keep")
    workspace = runner / "yuno-runner-retry"
    workspace.symlink_to(outside, target_is_directory=True)
    repository = FakeRepository(
        _intent(
            CleanupIntentKind.RUNNER_WORKSPACE,
            "runner-workspace:yuno-runner-retry",
        )
    )
    factory, state = _factory(repository)

    first = execute_pending_cleanup(
        factory,
        "owner-1",
        roots=ApprovedCleanupRoots(runner, tmp_path / "source"),
        completed_at="2026-08-13T12:00:00.000000Z",
    )

    assert first.failed == 1
    assert (outside / "sensitive").read_text() == "keep"
    failure = next(call for call in repository.calls if call[0] == "fail")
    assert failure[3] == "cleanup-path-not-approved"

    workspace.unlink()
    workspace.mkdir()
    (workspace / "temporary").write_text("remove")
    second = execute_pending_cleanup(
        factory,
        "owner-1",
        roots=ApprovedCleanupRoots(runner, tmp_path / "source"),
        completed_at="2026-08-13T12:01:00.000000Z",
    )

    assert not state["active"]
    assert second.completed == 1
    assert not workspace.exists()
    assert (outside / "sensitive").exists()

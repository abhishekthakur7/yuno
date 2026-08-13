"""Retention orchestration and out-of-transaction file cleanup."""

from __future__ import annotations

import errno
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from yuno.modules.data_lifecycle.domain import (
    CleanupIntent,
    CleanupIntentKind,
    CleanupRunResult,
    RetentionResult,
)
from yuno.modules.data_lifecycle.ports import (
    DataLifecycleUnitOfWork,
    DataLifecycleUnitOfWorkFactory,
)
from yuno.shared.domain.clock import utc_text
from yuno.shared.domain.hashing import hash_payload


@dataclass(frozen=True)
class RetentionPolicy:
    diagnostic_days: int = 30
    interview_days: int = 30
    terminal_job_days: int = 30
    job_event_days: int = 7
    job_event_owner_limit: int = 10_000
    runner_output_days: int = 7


@dataclass(frozen=True)
class ApprovedCleanupRoots:
    """Roots allowed for application-managed external data deletion."""

    runner: Path
    source: Path
    quarantine: Path | None = None


DEFAULT_RETENTION_POLICY = RetentionPolicy()


def runner_workspace_path_ref(raw_path: str | Path, root: Path) -> str | None:
    """Return a root-scoped logical reference without inspecting the filesystem."""
    path = Path(raw_path)
    approved_root = root.absolute()
    if (
        not path.is_absolute()
        or path.parent != approved_root
        or path.name in {"", ".", ".."}
        or not path.name.startswith("yuno-runner-")
    ):
        return None
    return f"runner-workspace:{path.name}"


def enforce_retention(
    uow: DataLifecycleUnitOfWork,
    owner_id: str,
    *,
    now: datetime,
    policy: RetentionPolicy = DEFAULT_RETENTION_POLICY,
) -> RetentionResult:
    """Apply one owner's database retention rules in the caller's UoW."""
    now_value = utc_text(now)
    repository = uow.data_lifecycle
    return RetentionResult(
        diagnostics=repository.expire_diagnostics(
            owner_id,
            utc_text(now - timedelta(days=policy.diagnostic_days)),
            now_value,
        ),
        interviews=repository.expire_interviews(
            owner_id, utc_text(now - timedelta(days=policy.interview_days))
        ),
        jobs=repository.purge_job_exhaust(
            owner_id, utc_text(now - timedelta(days=policy.terminal_job_days))
        ),
        events=repository.expire_job_events(
            owner_id,
            utc_text(now - timedelta(days=policy.job_event_days)),
            policy.job_event_owner_limit,
        ),
        runner_outputs=repository.expire_runner_outputs(
            owner_id, utc_text(now - timedelta(days=policy.runner_output_days))
        ),
        # These rows carry the exact completion-relative expiry timestamps.
        export_packages=repository.expire_export_packages(owner_id, now_value),
        export_operations=repository.expire_export_operations(owner_id, now_value),
    )


def run_retention_cycle(
    uow_factory: DataLifecycleUnitOfWorkFactory,
    owner_id: str,
    *,
    now: datetime,
    roots: ApprovedCleanupRoots,
    policy: RetentionPolicy = DEFAULT_RETENTION_POLICY,
) -> tuple[RetentionResult, CleanupRunResult]:
    """Commit database expiry, then perform pending file I/O separately."""
    with uow_factory() as uow:
        retained = enforce_retention(uow, owner_id, now=now, policy=policy)
        uow.commit()
    cleaned = execute_pending_cleanup(
        uow_factory, owner_id, roots=roots, completed_at=utc_text(now)
    )
    return retained, cleaned


def execute_pending_cleanup(
    uow_factory: DataLifecycleUnitOfWorkFactory,
    owner_id: str,
    *,
    roots: ApprovedCleanupRoots,
    completed_at: str,
) -> CleanupRunResult:
    """Retry durable cleanup intents without holding a SQLite transaction."""
    with uow_factory() as uow:
        intents = uow.data_lifecycle.list_pending_cleanup_intents(owner_id)

    completed = failed = 0
    for intent in intents:
        classification = _remove_approved_path(intent, roots)
        with uow_factory() as uow:
            if classification is None:
                changed = uow.data_lifecycle.finish_cleanup_intent(
                    owner_id, intent.id, completed_at
                )
                completed += int(changed)
            else:
                changed = uow.data_lifecycle.fail_cleanup_intent(
                    owner_id, intent.id, classification, completed_at
                )
                failed += int(changed)
            uow.commit()
    return CleanupRunResult(completed=completed, failed=failed)


def delete_import_bodies(
    uow: DataLifecycleUnitOfWork, owner_id: str, import_id: str
) -> int:
    removed = uow.data_lifecycle.purge_import_bodies(owner_id, import_id)
    uow.commit()
    return removed


def delete_interview_bodies(
    uow: DataLifecycleUnitOfWork, owner_id: str, run_id: str
) -> int:
    removed = uow.data_lifecycle.purge_interview_bodies(owner_id, run_id)
    uow.commit()
    return removed


def _remove_approved_path(
    intent: CleanupIntent, roots: ApprovedCleanupRoots
) -> str | None:
    resolved = _resolve_cleanup_path(intent, roots)
    if isinstance(resolved, str):
        return resolved
    path, allow_directory = resolved
    try:
        status = path.lstat()
    except FileNotFoundError:
        return None
    except PermissionError:
        return "cleanup-permission-denied"
    except OSError:
        return "cleanup-inspection-failed"

    if stat.S_ISLNK(status.st_mode):
        return "cleanup-path-not-approved"
    try:
        if stat.S_ISDIR(status.st_mode):
            if not allow_directory:
                return "cleanup-path-not-approved"
            shutil.rmtree(path)
        elif stat.S_ISREG(status.st_mode):
            path.unlink()
        else:
            return "cleanup-path-not-approved"
    except FileNotFoundError:
        return None
    except PermissionError:
        return "cleanup-permission-denied"
    except OSError as exc:
        if exc.errno in {errno.EBUSY, errno.ENOTEMPTY}:
            return "cleanup-path-busy"
        return "cleanup-io-failed"
    return None


def _resolve_cleanup_path(
    intent: CleanupIntent, roots: ApprovedCleanupRoots
) -> tuple[Path, bool] | str:
    if intent.path_hash != hash_payload(intent.path_ref):
        return "cleanup-reference-hash-mismatch"
    schemes: dict[CleanupIntentKind, tuple[str, Path | None, bool]] = {
        CleanupIntentKind.RUNNER_WORKSPACE: (
            "runner-workspace:",
            roots.runner,
            True,
        ),
        CleanupIntentKind.RUNNER_OUTPUT: ("runner-output:", roots.runner, False),
        CleanupIntentKind.SOURCE_SNAPSHOT: (
            "source-snapshot:",
            roots.source,
            False,
        ),
        CleanupIntentKind.PROVIDER_QUARANTINE: (
            "secure-provider-output:",
            roots.quarantine,
            False,
        ),
    }
    configured = schemes.get(intent.kind)
    if configured is None:
        return "cleanup-kind-not-external"
    prefix, root, allow_directory = configured
    if root is None:
        return "cleanup-root-not-configured"
    if not intent.path_ref.startswith(prefix):
        return "cleanup-reference-invalid"
    relative = intent.path_ref.removeprefix(prefix)
    if (
        not relative
        or relative in {".", ".."}
        or Path(relative).name != relative
        or Path(relative).is_absolute()
    ):
        return "cleanup-reference-invalid"
    if intent.kind is CleanupIntentKind.RUNNER_WORKSPACE and not relative.startswith(
        "yuno-runner-"
    ):
        return "cleanup-reference-invalid"
    if intent.kind in {
        CleanupIntentKind.SOURCE_SNAPSHOT,
        CleanupIntentKind.PROVIDER_QUARANTINE,
    } and (len(relative) != 64 or any(c not in "0123456789abcdef" for c in relative)):
        return "cleanup-reference-invalid"

    approved_root = root.resolve()
    candidate = approved_root / relative
    if candidate.parent.resolve() != approved_root:
        return "cleanup-path-not-approved"
    return candidate, allow_directory

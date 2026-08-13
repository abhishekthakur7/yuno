"""Domain values for lifecycle cleanup."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CleanupIntentStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class CleanupIntentKind(StrEnum):
    RUNNER_WORKSPACE = "runner-workspace"
    RUNNER_OUTPUT = "runner-output"
    GENERATED_ARTIFACT = "generated-artifact"
    EXPORT_PACKAGE = "export-package"
    SOURCE_SNAPSHOT = "source-snapshot"
    PROVIDER_QUARANTINE = "provider-quarantine"


@dataclass(frozen=True)
class CleanupIntent:
    id: str
    owner_id: str
    goal_id: str | None
    kind: CleanupIntentKind
    path_ref: str
    path_hash: str
    status: CleanupIntentStatus
    failure_classification: str | None
    attempts: int
    created_at: str
    updated_at: str
    completed_at: str | None


@dataclass(frozen=True)
class RetentionResult:
    diagnostics: int = 0
    interviews: int = 0
    jobs: int = 0
    events: int = 0
    runner_outputs: int = 0
    export_packages: int = 0
    export_operations: int = 0


@dataclass(frozen=True)
class CleanupRunResult:
    completed: int = 0
    failed: int = 0

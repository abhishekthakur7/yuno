from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from yuno.modules.runner.domain import ProcessLimits, RunnerProcessOutcome


@dataclass(frozen=True)
class RunnerProcessSpec:
    argv: tuple[str, ...]
    working_directory: Path
    environment: Mapping[str, str]
    limits: ProcessLimits
    phase: str


class ProcessPort(Protocol):
    def run(
        self,
        spec: RunnerProcessSpec,
        *,
        on_spawn: Callable[[int, int, str], None],
        cancelled: Callable[[], bool],
    ) -> RunnerProcessOutcome: ...


class TempWorkspacePort(Protocol):
    def create(self) -> Path: ...
    def cleanup(self, path: Path) -> None: ...


class WorkspaceCleanupIntentPort(Protocol):
    def record_workspace(
        self,
        *,
        owner_id: str,
        goal_id: str | None,
        path_ref: str,
        failure_classification: str | None,
        created_at: str,
    ) -> None: ...


WorkspaceCleanupIntentFactory = Callable[[object], WorkspaceCleanupIntentPort]

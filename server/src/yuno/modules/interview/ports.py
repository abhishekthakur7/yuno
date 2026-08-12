"""Interview repository ports."""

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.interview.domain import (
    InterviewBundle,
    InterviewIdempotencyRecord,
    PracticeRun,
    PracticeTurn,
    PracticeTurnResult,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class InterviewRepository(Protocol):
    def add_bundle(self, bundle: InterviewBundle) -> InterviewBundle: ...
    def get_bundle(self, owner_id: str, bundle_id: str) -> InterviewBundle | None: ...
    def list_bundles(
        self, owner_id: str, goal_id: str | None = None
    ) -> Sequence[InterviewBundle]: ...
    def update_bundle(
        self,
        owner_id: str,
        bundle_id: str,
        expected_version: int,
        changes: dict[str, object],
        item_changes: dict[str, bool],
    ) -> InterviewBundle | None: ...
    def delete_bundle(self, owner_id: str, bundle_id: str) -> bool: ...
    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> InterviewIdempotencyRecord | None: ...
    def add_idempotency(self, record: InterviewIdempotencyRecord) -> None: ...
    def add_run(self, run: PracticeRun) -> PracticeRun: ...
    def get_run(self, owner_id: str, run_id: str) -> PracticeRun | None: ...
    def add_turn(self, turn: PracticeTurn) -> PracticeTurn: ...
    def add_turn_result(self, result: PracticeTurnResult) -> PracticeTurnResult: ...
    def update_run(
        self, owner_id: str, run_id: str, changes: dict[str, object]
    ) -> PracticeRun | None: ...


class GoalView(Protocol):
    id: str


class GoalRepository(Protocol):
    def get_goal(self, owner_id: str, goal_id: str) -> GoalView | None: ...


class InterviewUnitOfWork(UnitOfWork, Protocol):
    interview: InterviewRepository
    profiles_goals: GoalRepository

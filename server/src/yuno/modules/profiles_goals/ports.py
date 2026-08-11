"""Repository and unit-of-work protocols for profiles and goals."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.profiles_goals.domain import (
    GoalNavigationEvent,
    GoalWorkspace,
    IdempotencyRecord,
    LearnerProfile,
    RecommendationDismissal,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class ProfilesGoalsRepository(Protocol):
    def get_profile(self, owner_id: str) -> LearnerProfile | None: ...
    def create_profile(self, owner_id: str) -> LearnerProfile: ...
    def update_profile(
        self, owner_id: str, expected_revision: int, changes: Mapping[str, object]
    ) -> LearnerProfile | None: ...
    def list_goals(self, owner_id: str) -> Sequence[GoalWorkspace]: ...
    def get_goal(self, owner_id: str, goal_id: str) -> GoalWorkspace | None: ...
    def create_goal(self, goal: GoalWorkspace) -> GoalWorkspace: ...
    def update_goal(
        self,
        owner_id: str,
        goal_id: str,
        expected_version: int,
        changes: Mapping[str, object],
    ) -> GoalWorkspace | None: ...
    def append_navigation(self, event: GoalNavigationEvent) -> None: ...
    def list_navigation(
        self, owner_id: str, goal_id: str
    ) -> Sequence[GoalNavigationEvent]: ...
    def add_dismissal(self, dismissal: RecommendationDismissal) -> bool: ...
    def list_dismissals(
        self, owner_id: str, goal_id: str
    ) -> Sequence[RecommendationDismissal]: ...
    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> IdempotencyRecord | None: ...
    def lock_idempotency_commands(self, owner_id: str) -> None: ...
    def add_idempotency(self, record: IdempotencyRecord) -> None: ...


class ProfilesGoalsUnitOfWork(UnitOfWork, Protocol):
    profiles_goals: ProfilesGoalsRepository
    audit: AuditRepository

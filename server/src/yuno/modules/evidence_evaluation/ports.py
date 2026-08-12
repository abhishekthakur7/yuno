"""Evidence persistence interfaces."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.evidence_evaluation.domain import (
    Evidence,
    EvidenceDeleteSnapshot,
    EvidencePayload,
    EvidenceTombstone,
    TransferredEvidenceRef,
    TransferredLearningState,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class EvidenceRepository(Protocol):
    def add_evidence(
        self, evidence: Evidence, payload: EvidencePayload
    ) -> Evidence: ...
    def get_evidence(
        self, owner_id: str, goal_id: str, evidence_id: str
    ) -> Evidence | None: ...
    def get_payload(
        self, owner_id: str, goal_id: str, evidence_id: str
    ) -> EvidencePayload | None: ...
    def list_evidence(self, owner_id: str, goal_id: str) -> Sequence[Evidence]: ...
    def add_tombstone(self, tombstone: EvidenceTombstone) -> None: ...
    def remove_payload(self, owner_id: str, goal_id: str, evidence_id: str) -> None: ...
    def list_tombstones(
        self, owner_id: str, goal_id: str
    ) -> Sequence[EvidenceTombstone]: ...
    def add_delete_snapshot(self, snapshot: EvidenceDeleteSnapshot) -> None: ...
    def get_delete_snapshot(
        self, owner_id: str, goal_id: str, snapshot_id: str
    ) -> EvidenceDeleteSnapshot | None: ...


class GoalView(Protocol):
    graph_version_id: str
    row_version: int
    status: object


class ProfileView(Protocol):
    current_goal_id: str | None
    profile_revision: int


class GoalLifecycleRepository(Protocol):
    def get_goal(self, owner_id: str, goal_id: str) -> GoalView | None: ...
    def get_goal_for_lifecycle(
        self, owner_id: str, goal_id: str
    ) -> GoalView | None: ...
    def tombstone_goal(
        self, owner_id: str, goal_id: str, expected_version: int
    ) -> GoalView | None: ...
    def get_profile(self, owner_id: str) -> ProfileView | None: ...
    def update_profile(
        self, owner_id: str, expected_revision: int, changes: dict[str, object]
    ) -> ProfileView | None: ...


class RoadmapTransferRepository(Protocol):
    def get_learning_state_for_topic(
        self, owner_id: str, goal_id: str, topic_stable_id: str
    ) -> object | None: ...
    def add_transferred_evidence(
        self,
        learning_state: TransferredLearningState,
        transfer_ref: TransferredEvidenceRef,
    ) -> None: ...
    def list_transfer_dependents(
        self, owner_id: str, source_goal_id: str
    ) -> Sequence[tuple[str, str]]: ...
    def downgrade_transfer_dependents(
        self, owner_id: str, source_goal_id: str, *, derived_at: str
    ) -> None: ...


class TopicView(Protocol):
    stable_id: str


class CanonicalReadRepository(Protocol):
    def get_published_topics(self, version_id: str) -> Sequence[TopicView]: ...


class EvidenceUnitOfWork(UnitOfWork, Protocol):
    evidence: EvidenceRepository
    audit: AuditRepository
    roadmap: RoadmapTransferRepository
    profiles_goals: GoalLifecycleRepository
    canonical: CanonicalReadRepository

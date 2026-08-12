"""Repository and UoW protocols for roadmap persistence."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.roadmap.domain import (
    LearnerCorrection,
    LearningState,
    OverlayEntry,
    PersonalOverlay,
    RoadmapIdempotencyRecord,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class RoadmapRepository(Protocol):
    def get_or_create_overlay(
        self, owner_id: str, goal_id: str, graph_version_id: str
    ) -> PersonalOverlay: ...
    def get_overlay(self, owner_id: str, goal_id: str) -> PersonalOverlay | None: ...
    def append_overlay_entry(self, entry: OverlayEntry) -> OverlayEntry: ...
    def list_overlay_entries(
        self, owner_id: str, goal_id: str
    ) -> Sequence[OverlayEntry]: ...
    def add_learning_state(self, state: LearningState) -> LearningState: ...
    def list_learning_states(
        self, owner_id: str, goal_id: str
    ) -> Sequence[LearningState]: ...
    def append_correction(self, correction: LearnerCorrection) -> LearnerCorrection: ...
    def list_corrections(
        self, owner_id: str, goal_id: str
    ) -> Sequence[LearnerCorrection]: ...
    def list_transferred_evidence_topic_ids(
        self, owner_id: str, goal_id: str
    ) -> Sequence[str]: ...
    def add_transferred_evidence(
        self,
        learning_state: TransferLearningStateView,
        transfer_ref: TransferEvidenceRefView,
    ) -> None: ...
    def get_learning_state_for_topic(
        self, owner_id: str, goal_id: str, topic_stable_id: str
    ) -> LearningState | None: ...
    def list_transfer_dependents(
        self, owner_id: str, source_goal_id: str
    ) -> Sequence[tuple[str, str]]: ...
    def downgrade_transfer_dependents(
        self, owner_id: str, source_goal_id: str, *, derived_at: str
    ) -> None: ...
    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> RoadmapIdempotencyRecord | None: ...
    def add_idempotency(self, record: RoadmapIdempotencyRecord) -> None: ...


class TransferClassificationView(Protocol):
    value: str


class TransferLearningStateView(Protocol):
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    graph_version_id: str
    classification: TransferClassificationView
    origin: str
    recommended_depth: str
    explanation: str
    derivation_version: str
    input_hash: str
    derived_at: str


class TransferEvidenceRefView(Protocol):
    id: str
    owner_id: str
    goal_id: str
    learning_state_id: str
    source_goal_id: str
    source_evidence_id: str
    classification: TransferClassificationView
    rationale: str
    created_at: str


class GoalView(Protocol):
    id: str
    graph_version_id: str


class GoalReadRepository(Protocol):
    def get_goal(self, owner_id: str, goal_id: str) -> GoalView | None: ...
    def lock_idempotency_commands(self, owner_id: str) -> None: ...


class CanonicalVersionView(Protocol):
    id: str


class CanonicalTopicView(Protocol):
    stable_id: str
    title: str
    subject: str
    scope_tags: tuple[str, ...]
    level_tag: str
    target_capability: str
    recommended_layer: str


class CanonicalRelationView(Protocol):
    from_stable_id: str
    to_stable_id: str
    relation_type: str


class CanonicalReadRepository(Protocol):
    def get_published_version(self, version_id: str) -> CanonicalVersionView | None: ...
    def list_published_versions(self) -> Sequence[CanonicalVersionView]: ...
    def get_published_topics(self, version_id: str) -> Sequence[CanonicalTopicView]: ...
    def get_published_relations(
        self, version_id: str
    ) -> Sequence[CanonicalRelationView]: ...


class RoadmapUnitOfWork(UnitOfWork, Protocol):
    roadmap: RoadmapRepository
    profiles_goals: GoalReadRepository
    canonical: CanonicalReadRepository

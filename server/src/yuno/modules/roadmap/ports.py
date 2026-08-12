"""Repository and UoW protocols for roadmap persistence."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.roadmap.domain import (
    LearnerCorrection,
    LearningState,
    OverlayEntry,
    OverlayProposal,
    OverlayProposalDecision,
    PersonalOverlay,
    RoadmapIdempotencyRecord,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class RoadmapRepository(Protocol):
    def get_or_create_overlay(
        self, owner_id: str, goal_id: str, graph_version_id: str
    ) -> PersonalOverlay: ...
    def get_overlay(self, owner_id: str, goal_id: str) -> PersonalOverlay | None: ...
    def advance_overlay_base(
        self, owner_id: str, goal_id: str, expected_version: int, graph_version_id: str
    ) -> PersonalOverlay | None: ...
    def append_overlay_entry(self, entry: OverlayEntry) -> OverlayEntry: ...
    def list_overlay_entries(
        self, owner_id: str, goal_id: str
    ) -> Sequence[OverlayEntry]: ...
    def add_proposal(self, proposal: OverlayProposal) -> OverlayProposal: ...
    def get_proposal(
        self, owner_id: str, proposal_id: str
    ) -> OverlayProposal | None: ...
    def get_pending_proposal_by_hash(
        self, owner_id: str, goal_id: str, content_hash: str
    ) -> OverlayProposal | None: ...
    def list_proposals(
        self, owner_id: str, goal_id: str
    ) -> Sequence[OverlayProposal]: ...
    def count_pending_proposals(self, owner_id: str, goal_id: str) -> int: ...
    def update_proposal_state(
        self,
        owner_id: str,
        proposal_id: str,
        expected_state: str,
        *,
        state: str,
        state_reason: str | None,
        decided_at: str,
    ) -> OverlayProposal | None: ...
    def append_proposal_decision(
        self, decision: OverlayProposalDecision
    ) -> OverlayProposalDecision: ...
    def list_proposal_decisions(
        self, owner_id: str, proposal_id: str
    ) -> Sequence[OverlayProposalDecision]: ...
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
    def list_progress_transfers(
        self, owner_id: str, goal_id: str
    ) -> Sequence[ProgressTransferView]: ...
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


@dataclass(frozen=True)
class ProgressTransferView:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    source_evidence_id: str
    classification: str
    rationale: str
    created_at: str


@dataclass(frozen=True)
class EvidenceTransferView:
    id: str
    target_goal_id: str
    learning_state_id: str
    classification: str
    rationale: str
    created_at: str


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
    audit: AuditRepository

"""Evidence persistence interfaces."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.evidence_evaluation.domain import (
    Assessment,
    AssessmentDimensionResult,
    AssessmentDispute,
    EvaluationRequest,
    EvaluationResult,
    Evidence,
    EvidenceDeleteSnapshot,
    EvidenceEvaluationIdempotencyRecord,
    EvidencePayload,
    EvidenceTombstone,
    GoalProgressMemo,
    ProgressEvidence,
    ReevaluationRequest,
    Rubric,
    RubricDimension,
    TransferredEvidenceRef,
    TransferredLearningState,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class EvidenceRepository(Protocol):
    def count_live_evidence(self, owner_id: str) -> int: ...
    def add_evidence(
        self, evidence: Evidence, payload: EvidencePayload
    ) -> Evidence: ...
    def get_evidence(
        self, owner_id: str, goal_id: str, evidence_id: str
    ) -> Evidence | None: ...
    def get_evidence_by_id(
        self, owner_id: str, evidence_id: str
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
    def add_rubric(
        self, rubric: Rubric, dimensions: Sequence[RubricDimension]
    ) -> Rubric: ...
    def get_rubric(self, owner_id: str, rubric_id: str) -> Rubric | None: ...
    def list_rubrics(self, owner_id: str) -> Sequence[Rubric]: ...
    def list_rubric_dimensions(
        self, owner_id: str, rubric_id: str
    ) -> Sequence[RubricDimension]: ...
    def add_assessment(
        self, assessment: Assessment, dimensions: Sequence[AssessmentDimensionResult]
    ) -> Assessment: ...
    def get_assessment(
        self, owner_id: str, assessment_id: str
    ) -> Assessment | None: ...
    def get_active_assessment_for_evidence(
        self, owner_id: str, evidence_id: str
    ) -> Assessment | None: ...
    def list_assessment_dimensions(
        self, owner_id: str, assessment_id: str
    ) -> Sequence[AssessmentDimensionResult]: ...
    def list_disputes(
        self, owner_id: str, assessment_id: str
    ) -> Sequence[AssessmentDispute]: ...
    def exclude_assessment(
        self, owner_id: str, goal_id: str, assessment_id: str
    ) -> None: ...
    def add_dispute(self, dispute: AssessmentDispute) -> AssessmentDispute: ...
    def get_dispute(
        self, owner_id: str, dispute_id: str
    ) -> AssessmentDispute | None: ...
    def add_reevaluation_request(
        self, request: ReevaluationRequest
    ) -> ReevaluationRequest: ...
    def get_reevaluation_request(
        self, owner_id: str, request_id: str
    ) -> ReevaluationRequest | None: ...
    def get_reevaluation_for_dispute(
        self, owner_id: str, dispute_id: str
    ) -> ReevaluationRequest | None: ...
    def update_reevaluation_request(
        self, owner_id: str, request_id: str, changes: dict[str, object]
    ) -> None: ...
    def add_idempotency(self, record: EvidenceEvaluationIdempotencyRecord) -> None: ...
    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> EvidenceEvaluationIdempotencyRecord | None: ...
    def complete_idempotency(
        self, owner_id: str, operation: str, key: str, response_json: str
    ) -> None: ...
    def list_pending_idempotency(
        self, operation_prefix: str
    ) -> Sequence[EvidenceEvaluationIdempotencyRecord]: ...
    def list_progress_evidence(
        self, owner_id: str, goal_id: str
    ) -> Sequence[ProgressEvidence]: ...
    def get_progress_memo(
        self, owner_id: str, goal_id: str
    ) -> GoalProgressMemo | None: ...
    def put_progress_memo(self, memo: GoalProgressMemo) -> None: ...


class EvaluationAdapter(Protocol):
    """Evaluation provider boundary."""

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult: ...


class GoalView(Protocol):
    graph_version_id: str
    row_version: int
    status: object


class ProfileView(Protocol):
    current_goal_id: str | None
    profile_revision: int


class GoalLifecycleRepository(Protocol):
    def lock_idempotency_commands(self, owner_id: str) -> None: ...
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
    def list_corrections(self, owner_id: str, goal_id: str) -> Sequence[object]: ...
    def list_learning_states(self, owner_id: str, goal_id: str) -> Sequence[object]: ...
    def list_transferred_evidence_topic_ids(
        self, owner_id: str, goal_id: str
    ) -> Sequence[str]: ...
    def list_progress_transfers(
        self, owner_id: str, goal_id: str
    ) -> Sequence[object]: ...
    def list_evidence_transfers(
        self, owner_id: str, evidence_id: str
    ) -> Sequence[object]: ...


class TopicView(Protocol):
    stable_id: str


class CanonicalReadRepository(Protocol):
    def get_published_topics(self, version_id: str) -> Sequence[TopicView]: ...


class GoalBodyLifecycleRepository(Protocol):
    def purge_goal_bodies(self, owner_id: str, goal_id: str, now: str) -> int: ...


class EvidenceUnitOfWork(UnitOfWork, Protocol):
    evidence: EvidenceRepository
    audit: AuditRepository
    roadmap: RoadmapTransferRepository
    profiles_goals: GoalLifecycleRepository
    canonical: CanonicalReadRepository
    data_lifecycle: GoalBodyLifecycleRepository

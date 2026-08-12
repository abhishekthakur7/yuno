"""Evidence persistence models."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import Base, boolean_column, utc_timestamp_column


class EvidenceRow(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_evidence_goal_owner",
        ),
        UniqueConstraint("id", "owner_id", "goal_id", name="uq_evidence_id_owner_goal"),
        CheckConstraint(
            "length(trim(evidence_type)) > 0", name="evidence_type_non_blank"
        ),
        CheckConstraint(
            "capability IN ('know','understand','choose','implement','diagnose','defend')",
            name="capability_valid",
        ),
        CheckConstraint(
            "length(trim(payload_hash)) > 0", name="payload_hash_non_blank"
        ),
        CheckConstraint("length(trim(origin)) > 0", name="origin_non_blank"),
        Index(
            "ix_evidence_owner_goal_topic_created",
            "owner_id",
            "goal_id",
            "topic_stable_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str] = mapped_column(
        Text, ForeignKey("topic_identities.stable_id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class EvidencePayloadRow(Base):
    __tablename__ = "evidence_payloads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_evidence_payloads_evidence_owner_goal",
        ),
        UniqueConstraint(
            "evidence_id",
            "owner_id",
            "goal_id",
            name="uq_evidence_payloads_evidence_owner_goal",
        ),
        CheckConstraint(
            "length(trim(content_version)) > 0", name="content_version_non_blank"
        ),
    )

    evidence_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_version: Mapped[str] = mapped_column(Text, nullable=False)


class EvidenceTombstoneRow(Base):
    __tablename__ = "evidence_tombstones"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_evidence_tombstones_evidence_owner_goal",
        ),
        UniqueConstraint(
            "evidence_id",
            "owner_id",
            "goal_id",
            name="uq_evidence_tombstones_evidence_owner_goal",
        ),
        CheckConstraint(
            "length(trim(delete_operation_id)) > 0",
            name="delete_operation_id_non_blank",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="reason_non_blank"),
    )

    evidence_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    delete_operation_id: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    tombstoned_at: Mapped[str] = utc_timestamp_column()


class EvidenceDeleteSnapshotRow(Base):
    __tablename__ = "evidence_delete_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_evidence_delete_snapshots_goal_owner",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_evidence_delete_snapshots_id_owner_goal",
        ),
        CheckConstraint("json_valid(impact_json)", name="impact_json_valid"),
        CheckConstraint("json_type(impact_json) = 'object'", name="impact_json_object"),
        CheckConstraint("length(trim(impact_hash)) > 0", name="impact_hash_non_blank"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    impact_json: Mapped[str] = mapped_column(Text, nullable=False)
    impact_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class RubricRow(Base):
    __tablename__ = "rubrics"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_rubrics_id_owner"),
        UniqueConstraint(
            "owner_id", "task_context", "capability", "role_context", "level_context", "version",
            name="uq_rubrics_context_version",
        ),
        CheckConstraint("length(trim(task_context)) > 0", name="task_context_non_blank"),
        CheckConstraint("length(trim(capability)) > 0", name="capability_non_blank"),
        CheckConstraint("length(trim(version)) > 0", name="version_non_blank"),
        CheckConstraint("status IN ('fixture','approved','retired')", name="status_valid"),
        CheckConstraint("length(trim(provenance)) > 0", name="provenance_non_blank"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    task_context: Mapped[str] = mapped_column(Text, nullable=False)
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    role_context: Mapped[str | None] = mapped_column(Text)
    level_context: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class RubricDimensionRow(Base):
    __tablename__ = "rubric_dimensions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rubric_id", "owner_id"], ["rubrics.id", "rubrics.owner_id"],
            name="fk_rubric_dimensions_rubric_owner",
        ),
        UniqueConstraint("id", "owner_id", name="uq_rubric_dimensions_id_owner"),
        UniqueConstraint("rubric_id", "stable_dimension_id", name="uq_rubric_dimensions_stable"),
        UniqueConstraint("rubric_id", "ordinal", name="uq_rubric_dimensions_ordinal"),
        CheckConstraint("length(trim(stable_dimension_id)) > 0", name="stable_id_non_blank"),
        CheckConstraint("length(trim(name)) > 0", name="name_non_blank"),
        CheckConstraint("ordinal > 0", name="ordinal_positive"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    rubric_id: Mapped[str] = mapped_column(Text, nullable=False)
    stable_dimension_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluation_guidance: Mapped[str] = mapped_column(Text, nullable=False)


class AssessmentRow(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_assessments_goal_owner",
        ),
        ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_assessments_evidence_owner_goal",
        ),
        ForeignKeyConstraint(
            ["rubric_id", "owner_id"], ["rubrics.id", "rubrics.owner_id"],
            name="fk_assessments_rubric_owner",
        ),
        ForeignKeyConstraint(
            ["predecessor_assessment_id", "owner_id", "goal_id"],
            ["assessments.id", "assessments.owner_id", "assessments.goal_id"],
            name="fk_assessments_predecessor_owner_goal",
        ),
        UniqueConstraint("id", "owner_id", "goal_id", name="uq_assessments_id_owner_goal"),
        UniqueConstraint("predecessor_assessment_id", name="uq_assessments_predecessor"),
        CheckConstraint("state IN ('feedback-ready','ambiguity-unresolved')", name="state_valid"),
        CheckConstraint("json_valid(assumptions_json)", name="assumptions_json_valid"),
        CheckConstraint("json_valid(source_refs_json)", name="source_refs_json_valid"),
        CheckConstraint("json_valid(provenance_refs_json)", name="provenance_refs_json_valid"),
        CheckConstraint("json_valid(facts_json)", name="facts_json_valid"),
        CheckConstraint("json_valid(trade_offs_json)", name="trade_offs_json_valid"),
        CheckConstraint("json_valid(citations_json)", name="citations_json_valid"),
        CheckConstraint("json_valid(ambiguities_json)", name="ambiguities_json_valid"),
        CheckConstraint("json_valid(warnings_json)", name="warnings_json_valid"),
        CheckConstraint("json_valid(limitation_labels_json)", name="limitation_labels_json_valid"),
        Index("ix_assessments_owner_goal_evidence_created", "owner_id", "goal_id", "evidence_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str | None] = mapped_column(Text)
    rubric_id: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_version: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    task_ref: Mapped[str] = mapped_column(Text, nullable=False)
    requested_capability: Mapped[str] = mapped_column(Text, nullable=False)
    role_context: Mapped[str | None] = mapped_column(Text)
    level_context: Mapped[str | None] = mapped_column(Text)
    evaluation_method: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_refs_json: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_refs_json: Mapped[str] = mapped_column(Text, nullable=False)
    facts_json: Mapped[str] = mapped_column(Text, nullable=False)
    trade_offs_json: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[str] = mapped_column(Text, nullable=False)
    ambiguities_json: Mapped[str] = mapped_column(Text, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    cross_question_candidate: Mapped[str | None] = mapped_column(Text)
    revision_invitation: Mapped[str | None] = mapped_column(Text)
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False)
    limitation_labels_json: Mapped[str] = mapped_column(Text, nullable=False)
    predecessor_assessment_id: Mapped[str | None] = mapped_column(Text)
    derivation_excluded: Mapped[int] = boolean_column("derivation_excluded", default=False)
    created_at: Mapped[str] = utc_timestamp_column()


class AssessmentDimensionResultRow(Base):
    __tablename__ = "assessment_dimension_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_assessment_dimension_results_goal_owner",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "owner_id", "goal_id"],
            ["assessments.id", "assessments.owner_id", "assessments.goal_id"],
            name="fk_assessment_dimension_results_assessment_owner_goal",
        ),
        ForeignKeyConstraint(
            ["rubric_dimension_id", "owner_id"],
            ["rubric_dimensions.id", "rubric_dimensions.owner_id"],
            name="fk_assessment_dimension_results_dimension_owner",
        ),
        UniqueConstraint("id", "owner_id", "goal_id", name="uq_assessment_dimension_results_id_owner_goal"),
        UniqueConstraint("assessment_id", "rubric_dimension_id", name="uq_assessment_dimension_results_dimension"),
        CheckConstraint("outcome IN ('pass','trade-off','factual-correction','ambiguity-unresolved')", name="outcome_valid"),
        CheckConstraint("json_valid(evidence_refs_json)", name="evidence_refs_json_valid"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_id: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_dimension_id: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs_json: Mapped[str] = mapped_column(Text, nullable=False)


class AssessmentDisputeRow(Base):
    __tablename__ = "assessment_disputes"
    __table_args__ = (
        ForeignKeyConstraint(["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"], name="fk_assessment_disputes_goal_owner"),
        ForeignKeyConstraint(["assessment_id", "owner_id", "goal_id"], ["assessments.id", "assessments.owner_id", "assessments.goal_id"], name="fk_assessment_disputes_assessment_owner_goal"),
        UniqueConstraint("id", "owner_id", "goal_id", name="uq_assessment_disputes_id_owner_goal"),
        CheckConstraint("status IN ('requested')", name="status_valid"),
        CheckConstraint("length(trim(reason)) > 0", name="reason_non_blank"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_id: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[str] = utc_timestamp_column()
    resolved_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)


class ReevaluationRequestRow(Base):
    __tablename__ = "reevaluation_requests"
    __table_args__ = (
        ForeignKeyConstraint(["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"], name="fk_reevaluation_requests_goal_owner"),
        ForeignKeyConstraint(["dispute_id", "owner_id", "goal_id"], ["assessment_disputes.id", "assessment_disputes.owner_id", "assessment_disputes.goal_id"], name="fk_reevaluation_requests_dispute_owner_goal"),
        ForeignKeyConstraint(["prior_assessment_id", "owner_id", "goal_id"], ["assessments.id", "assessments.owner_id", "assessments.goal_id"], name="fk_reevaluation_requests_prior_owner_goal"),
        ForeignKeyConstraint(["resulting_assessment_id", "owner_id", "goal_id"], ["assessments.id", "assessments.owner_id", "assessments.goal_id"], name="fk_reevaluation_requests_result_owner_goal"),
        UniqueConstraint("id", "owner_id", "goal_id", name="uq_reevaluation_requests_id_owner_goal"),
        UniqueConstraint("dispute_id", name="uq_reevaluation_requests_dispute"),
        UniqueConstraint("job_id", name="uq_reevaluation_requests_job"),
        CheckConstraint("status IN ('requested','completed','failed')", name="status_valid"),
        CheckConstraint("status != 'completed' OR (resulting_assessment_id IS NOT NULL AND completed_at IS NOT NULL)", name="completed_has_result"),
        CheckConstraint("status != 'failed' OR failure_reference IS NOT NULL", name="failed_has_reference"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    dispute_id: Mapped[str] = mapped_column(Text, nullable=False)
    prior_assessment_id: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    resulting_assessment_id: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[str] = utc_timestamp_column()
    completed_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    failure_reference: Mapped[str | None] = mapped_column(Text)


class EvidenceEvaluationIdempotencyRow(Base):
    __tablename__ = "evidence_evaluation_idempotency"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_evidence_evaluation_idempotency_id_owner"),
        UniqueConstraint("owner_id", "operation", "idempotency_key", name="uq_evidence_evaluation_idempotency_command"),
        CheckConstraint("length(trim(operation)) > 0", name="operation_non_blank"),
        CheckConstraint("json_valid(response_json)", name="response_json_valid"),
        CheckConstraint("completed IN (0,1)", name="completed_in_0_1"),
        CheckConstraint("completed = 1 OR request_ref IS NOT NULL", name="reservation_has_request_ref"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()
    request_ref: Mapped[str | None] = mapped_column(Text)
    completed: Mapped[int] = boolean_column("completed", default=True)


class GoalProgressMemoRow(Base):
    __tablename__ = "goal_progress_memos"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_goal_progress_memos_goal_owner",
        ),
        UniqueConstraint("goal_id", "owner_id", name="uq_goal_progress_memos_goal_owner"),
        CheckConstraint("coverage IN ('likely-known','partial','unverified','new')", name="coverage_valid"),
        CheckConstraint("proficiency IN ('likely-known','partial','unverified','new')", name="proficiency_valid"),
        CheckConstraint("retention IN ('likely-known','partial','unverified','new')", name="retention_valid"),
        CheckConstraint("readiness IN ('likely-known','partial','unverified','new')", name="readiness_valid"),
        CheckConstraint("json_valid(explanation_json)", name="explanation_json_valid"),
        CheckConstraint("length(trim(input_hash)) > 0", name="input_hash_non_blank"),
        CheckConstraint("length(trim(derivation_version)) > 0", name="derivation_version_non_blank"),
    )
    goal_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    coverage: Mapped[str] = mapped_column(Text, nullable=False)
    proficiency: Mapped[str] = mapped_column(Text, nullable=False)
    retention: Mapped[str] = mapped_column(Text, nullable=False)
    readiness: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    derivation_version: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[str] = utc_timestamp_column()

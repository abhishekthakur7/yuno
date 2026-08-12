"""SQLAlchemy persistence models for learner-owned roadmap state."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import (
    Base,
    id_column,
    row_version_column,
    utc_timestamp_column,
)


class PersonalOverlayRow(Base):
    __tablename__ = "personal_overlays"
    __table_args__ = (
        CheckConstraint("state IN ('active')", name="state_valid"),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_personal_overlays_goal_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_personal_overlays_id_owner_goal"
        ),
        UniqueConstraint("owner_id", "goal_id", name="uq_personal_overlays_owner_goal"),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    base_graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("editorial_approvals.graph_version_id"), nullable=False
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    row_version: Mapped[int] = row_version_column()
    created_at: Mapped[str] = utc_timestamp_column()


class OverlayEntryRow(Base):
    __tablename__ = "overlay_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('order_constraint','skip','depth','bridge','recommendation')",
            name="entry_type_valid",
        ),
        CheckConstraint(
            "source IN ('learner','diagnostic_confirmation','overlay_proposal')",
            name="source_valid",
        ),
        CheckConstraint("json_valid(value_json)", name="value_json_valid"),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_overlay_entries_goal_owner",
        ),
        ForeignKeyConstraint(
            ["overlay_id", "owner_id", "goal_id"],
            [
                "personal_overlays.id",
                "personal_overlays.owner_id",
                "personal_overlays.goal_id",
            ],
            name="fk_overlay_entries_overlay_owner_goal",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_overlay_entries_id_owner_goal"
        ),
        UniqueConstraint(
            "owner_id",
            "goal_id",
            "content_hash",
            name="uq_overlay_entries_content_hash",
        ),
        Index(
            "ix_overlay_entries_owner_goal_approved",
            "owner_id",
            "goal_id",
            "approved_at",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    overlay_id: Mapped[str] = mapped_column(Text, nullable=False)
    graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("editorial_approvals.graph_version_id"), nullable=False
    )
    topic_stable_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_type: Mapped[str] = mapped_column(Text, nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[str] = utc_timestamp_column()
    supersedes_entry_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("overlay_entries.id")
    )
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)


class OverlayProposalRow(Base):
    __tablename__ = "overlay_proposals"
    __table_args__ = (
        CheckConstraint(
            "proposal_type IN ('recommendation','emphasis','example','exercise','ordering','bridge')",
            name="proposal_type_valid",
        ),
        CheckConstraint(
            "state IN ('awaiting-learner-decision','accepted','postponed','dismissed','rejected-stale')",
            name="state_valid",
        ),
        CheckConstraint("json_valid(payload_json)", name="payload_json_valid"),
        CheckConstraint(
            "json_type(payload_json) = 'object'", name="payload_json_object"
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_overlay_proposals_goal_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_overlay_proposals_id_owner_goal"
        ),
        Index(
            "uq_overlay_proposals_pending_goal_hash",
            "goal_id",
            "content_hash",
            unique=True,
            sqlite_where=sql_text("state = 'awaiting-learner-decision'"),
        ),
        Index(
            "ix_overlay_proposals_owner_goal_state_created",
            "owner_id",
            "goal_id",
            "state",
            "created_at",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    generated_against_graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("editorial_approvals.graph_version_id"), nullable=False
    )
    topic_stable_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposal_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    state_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = utc_timestamp_column()
    decided_at: Mapped[str | None] = utc_timestamp_column(nullable=True)


class OverlayProposalDecisionRow(Base):
    __tablename__ = "overlay_proposal_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('accept','add','postpone','dismiss')", name="decision_valid"
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_overlay_proposal_decisions_goal_owner",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "owner_id", "goal_id"],
            [
                "overlay_proposals.id",
                "overlay_proposals.owner_id",
                "overlay_proposals.goal_id",
            ],
            name="fk_overlay_proposal_decisions_proposal_owner_goal",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_overlay_proposal_decisions_id_owner_goal",
        ),
        Index(
            "ix_overlay_proposal_decisions_owner_proposal_decided",
            "owner_id",
            "proposal_id",
            "decided_at",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_id: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[str] = utc_timestamp_column()


class LearningStateRow(Base):
    __tablename__ = "learning_states"
    __table_args__ = (
        CheckConstraint(
            "classification IN ('likely-known','partial','unverified','new')",
            name="classification_valid",
        ),
        CheckConstraint("length(trim(origin)) > 0", name="origin_non_blank"),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_learning_states_goal_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_learning_states_id_owner_goal"
        ),
        UniqueConstraint(
            "owner_id",
            "goal_id",
            "topic_stable_id",
            name="uq_learning_states_goal_topic",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str] = mapped_column(Text, nullable=False)
    graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("editorial_approvals.graph_version_id"), nullable=False
    )
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_depth: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    derivation_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    derived_at: Mapped[str] = utc_timestamp_column()


class LearnerCorrectionRow(Base):
    __tablename__ = "learner_corrections"
    __table_args__ = (
        CheckConstraint(
            "correction_type IN ('correction','confirmation','gap','transfer-confirmation')",
            name="correction_type_valid",
        ),
        CheckConstraint(
            "value IN ('likely-known','partial','unverified','new')", name="value_valid"
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_learner_corrections_goal_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_learner_corrections_id_owner_goal"
        ),
        Index(
            "ix_learner_corrections_owner_goal_topic",
            "owner_id",
            "goal_id",
            "topic_stable_id",
            "created_at",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str] = mapped_column(Text, nullable=False)
    correction_type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = utc_timestamp_column()
    supersedes_correction_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("learner_corrections.id")
    )


class TransferredEvidenceRefRow(Base):
    __tablename__ = "transferred_evidence_refs"
    __table_args__ = (
        CheckConstraint(
            "classification IN ('likely-known','partial','unverified','new')",
            name="classification_valid",
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_transferred_evidence_refs_goal_owner",
        ),
        ForeignKeyConstraint(
            ["learning_state_id", "owner_id", "goal_id"],
            [
                "learning_states.id",
                "learning_states.owner_id",
                "learning_states.goal_id",
            ],
            name="fk_transferred_evidence_refs_state_owner_goal",
        ),
        ForeignKeyConstraint(
            ["source_goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_transferred_evidence_refs_source_goal_owner",
        ),
        ForeignKeyConstraint(
            ["source_evidence_id", "owner_id", "source_goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_transferred_evidence_refs_source_evidence_owner_goal",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_transferred_evidence_refs_id_owner_goal",
        ),
        UniqueConstraint(
            "learning_state_id",
            "source_evidence_id",
            name="uq_transferred_evidence_refs_state_evidence",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    learning_state_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_evidence_id: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class RoadmapIdempotencyRow(Base):
    __tablename__ = "roadmap_idempotency"
    __table_args__ = (
        CheckConstraint("length(trim(operation)) > 0", name="operation_non_blank"),
        CheckConstraint(
            "length(trim(idempotency_key)) > 0", name="idempotency_key_non_blank"
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_roadmap_idempotency_goal_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_roadmap_idempotency_id_owner_goal"
        ),
        UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_roadmap_idempotency_command",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()

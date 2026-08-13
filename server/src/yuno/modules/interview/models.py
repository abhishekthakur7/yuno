"""SQLAlchemy models for interview preparation bundles."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yuno.shared.infrastructure.base import (
    Base,
    boolean_column,
    id_column,
    row_version_column,
    utc_timestamp_column,
)


class InterviewBundleRow(Base):
    __tablename__ = "interview_bundles"
    __table_args__ = (
        CheckConstraint("status IN ('active','archived')", name="status_valid"),
        CheckConstraint(
            "target_level IN ('Mid-level','Senior','Staff')", name="target_level_valid"
        ),
        UniqueConstraint("id", "owner_id", name="uq_interview_bundles_id_owner"),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_interview_bundles_goal_owner",
        ),
        ForeignKeyConstraint(
            ["copy_source_id", "owner_id"],
            ["interview_bundles.id", "interview_bundles.owner_id"],
            name="fk_interview_bundles_copy_source_owner",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    goal_id: Mapped[str | None] = mapped_column(Text)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    target_level: Mapped[str] = mapped_column(Text, nullable=False)
    copy_source_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    row_version: Mapped[int] = row_version_column()
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()
    items: Mapped[list[InterviewBundleItemRow]] = relationship(
        cascade="all, delete-orphan", order_by="InterviewBundleItemRow.position"
    )


class InterviewBundleItemRow(Base):
    __tablename__ = "interview_bundle_items"
    __table_args__ = (
        CheckConstraint(
            "subject IN ('technical','behavioral','leadership')", name="subject_valid"
        ),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint("is_optional IN (0,1)", name="is_optional_valid"),
        CheckConstraint("included IN (0,1)", name="included_valid"),
        CheckConstraint(
            "subject = 'technical' OR is_optional = 1", name="nontechnical_optional"
        ),
        UniqueConstraint("id", "owner_id", name="uq_interview_bundle_items_id_owner"),
        UniqueConstraint(
            "bundle_id",
            "owner_id",
            "position",
            name="uq_interview_bundle_items_bundle_owner_position",
        ),
        ForeignKeyConstraint(
            ["bundle_id", "owner_id"],
            ["interview_bundles.id", "interview_bundles.owner_id"],
            ondelete="CASCADE",
            name="fk_interview_bundle_items_bundle_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    bundle_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str | None] = mapped_column(Text)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_optional: Mapped[int] = boolean_column("is_optional", default=False)
    included: Mapped[int] = boolean_column("included", default=True)


class InterviewBundleBodyRow(Base):
    __tablename__ = "interview_bundle_bodies"
    bundle_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    generic_role: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["bundle_id", "owner_id"],
            ["interview_bundles.id", "interview_bundles.owner_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("length(trim(name)) > 0", name="name_non_blank"),
        CheckConstraint(
            "length(trim(generic_role)) > 0", name="generic_role_non_blank"
        ),
        CheckConstraint("length(trim(origin)) > 0", name="origin_non_blank"),
    )


class InterviewBundleItemBodyRow(Base):
    __tablename__ = "interview_bundle_item_bodies"
    item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    question: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "owner_id"],
            ["interview_bundle_items.id", "interview_bundle_items.owner_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "question IS NULL OR length(trim(question)) > 0", name="question_non_blank"
        ),
    )


class InterviewIdempotencyRow(Base):
    __tablename__ = "interview_idempotency"
    __table_args__ = (
        CheckConstraint("length(trim(operation)) > 0", name="operation_non_blank"),
        CheckConstraint("length(trim(idempotency_key)) > 0", name="key_non_blank"),
        UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_interview_idempotency_owner_operation_key",
        ),
        UniqueConstraint("id", "owner_id", name="uq_interview_idempotency_id_owner"),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    response_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class InterviewRunRow(Base):
    __tablename__ = "interview_runs"
    __table_args__ = (
        CheckConstraint("mode IN ('Practice','Mock')", name="mode_valid"),
        CheckConstraint(
            "(mode = 'Practice' AND state IN ('ready','answering','follow-up','submitted','evaluating','feedback-ready','failed-recoverable')) OR "
            "(mode = 'Mock' AND state IN ('ready','answering','follow-up','paused','completing','completed','failed-recoverable'))",
            name="state_valid",
        ),
        CheckConstraint(
            "(mode = 'Practice' AND rubric_id IS NOT NULL AND rubric_version IS NOT NULL) OR "
            "(mode = 'Mock' AND ((rubric_id IS NULL AND rubric_version IS NULL) OR "
            "(rubric_id IS NOT NULL AND rubric_version IS NOT NULL)))",
            name="mode_references_valid",
        ),
        CheckConstraint(
            "mode != 'Mock' OR state != 'completed' OR final_assessment_id IS NOT NULL",
            name="mock_completed_assessment",
        ),
        CheckConstraint("retryable IN (0,1)", name="retryable_valid"),
        UniqueConstraint("id", "owner_id", name="uq_interview_runs_id_owner"),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_interview_runs_id_owner_goal"
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_interview_runs_goal_owner",
        ),
        ForeignKeyConstraint(
            ["bundle_id", "owner_id"],
            ["interview_bundles.id", "interview_bundles.owner_id"],
            name="fk_interview_runs_bundle_owner",
        ),
        ForeignKeyConstraint(
            ["bundle_item_id", "owner_id"],
            ["interview_bundle_items.id", "interview_bundle_items.owner_id"],
            name="fk_interview_runs_item_owner",
        ),
        ForeignKeyConstraint(
            ["final_assessment_id", "owner_id", "goal_id"],
            ["assessments.id", "assessments.owner_id", "assessments.goal_id"],
            name="fk_interview_runs_final_assessment_owner_goal",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    goal_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    bundle_id: Mapped[str] = mapped_column(Text, nullable=False)
    bundle_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="Practice")
    state: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_id: Mapped[str | None] = mapped_column(Text)
    rubric_version: Mapped[str | None] = mapped_column(Text)
    requested_capability: Mapped[str] = mapped_column(Text, nullable=False)
    active_job_id: Mapped[str | None] = mapped_column(Text)
    active_answer_turn_id: Mapped[str | None] = mapped_column(Text)
    failure_reference: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[int] = boolean_column("retryable", default=False)
    body_hash: Mapped[str | None] = mapped_column(Text)
    final_assessment_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class InterviewTurnRow(Base):
    __tablename__ = "interview_turns"
    __table_args__ = (
        CheckConstraint("turn_number >= 1", name="turn_number_positive"),
        CheckConstraint(
            "kind IN ('question','answer','hint','follow-up')", name="kind_valid"
        ),
        UniqueConstraint("id", "owner_id", name="uq_interview_turns_id_owner"),
        UniqueConstraint("run_id", "turn_number", name="uq_interview_turns_run_number"),
        ForeignKeyConstraint(
            ["run_id", "owner_id"],
            ["interview_runs.id", "interview_runs.owner_id"],
            ondelete="CASCADE",
            name="fk_interview_turns_run_owner",
        ),
        ForeignKeyConstraint(
            ["answer_turn_id", "owner_id"],
            ["interview_turns.id", "interview_turns.owner_id"],
            name="fk_interview_turns_answer_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str | None] = mapped_column(Text)
    answer_turn_id: Mapped[str | None] = mapped_column(Text)
    evidence_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = utc_timestamp_column()


class InterviewTurnResultRow(Base):
    __tablename__ = "interview_turn_results"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_interview_turn_results_id_owner"),
        UniqueConstraint("answer_turn_id", name="uq_interview_turn_results_answer"),
        ForeignKeyConstraint(
            ["run_id", "owner_id"],
            ["interview_runs.id", "interview_runs.owner_id"],
            ondelete="CASCADE",
            name="fk_interview_turn_results_run_owner",
        ),
        ForeignKeyConstraint(
            ["answer_turn_id", "owner_id"],
            ["interview_turns.id", "interview_turns.owner_id"],
            name="fk_interview_turn_results_answer_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    answer_turn_id: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_id: Mapped[str] = mapped_column(Text, nullable=False)
    visible_at: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str | None] = mapped_column(Text)

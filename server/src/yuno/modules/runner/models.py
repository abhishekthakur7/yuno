from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import Base, id_column, utc_timestamp_column


class RunnerConfirmationRow(Base):
    __tablename__ = "runner_confirmations"
    __table_args__ = (
        CheckConstraint(
            "language IN ('java','python','relational')", name="language_valid"
        ),
        CheckConstraint("operation IN ('compile','test')", name="operation_valid"),
        UniqueConstraint("id", "owner_id", name="uq_runner_confirmations_id_owner"),
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_runner_confirmations_owner_idempotency",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str | None] = mapped_column(Text)
    artifact_id: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_hash: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledgement_version: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    request_hash: Mapped[str | None] = mapped_column(Text)
    reserved_run_id: Mapped[str | None] = mapped_column(Text)
    environment_policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    limits_config_version: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_at: Mapped[str] = utc_timestamp_column()
    expires_at: Mapped[str] = utc_timestamp_column()
    consumed_at: Mapped[str | None] = utc_timestamp_column(nullable=True)


class RunnerRecordRow(Base):
    __tablename__ = "runner_records"
    __table_args__ = (
        CheckConstraint(
            "language IN ('java','python','relational')", name="language_valid"
        ),
        CheckConstraint("operation IN ('compile','test')", name="operation_valid"),
        CheckConstraint(
            "state IN ('queued','preparing','running','completed','failed','timed-out-or-limited','cancel-requested','cancelled')",
            name="state_valid",
        ),
        CheckConstraint(
            "cleanup_state IN ('cleanup-pending','cleanup-complete','cleanup-failed')",
            name="cleanup_state_valid",
        ),
        UniqueConstraint("id", "owner_id", name="uq_runner_records_id_owner"),
        UniqueConstraint("job_id", name="uq_runner_records_job"),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str | None] = mapped_column(Text)
    artifact_id: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    confirmation_id: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    toolchain: Mapped[str] = mapped_column(Text, nullable=False)
    argv_json: Mapped[str] = mapped_column(Text, nullable=False)
    working_directory_policy: Mapped[str] = mapped_column(Text, nullable=False)
    environment_policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    limits_config_version: Mapped[str] = mapped_column(Text, nullable=False)
    pid: Mapped[int | None] = mapped_column(Integer)
    pgid: Mapped[int | None] = mapped_column(Integer)
    temp_path: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    outcome_json: Mapped[str | None] = mapped_column(Text)
    cleanup_state: Mapped[str] = mapped_column(Text, nullable=False)
    cleanup_diagnostic: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class RunnerConfirmationInputRow(Base):
    __tablename__ = "runner_confirmation_inputs"
    __table_args__ = (
        UniqueConstraint(
            "id", "owner_id", name="uq_runner_confirmation_inputs_id_owner"
        ),
        UniqueConstraint(
            "confirmation_id",
            "logical_path",
            name="uq_runner_confirmation_inputs_confirmation_path",
        ),
        ForeignKeyConstraint(
            ["confirmation_id", "owner_id"],
            ["runner_confirmations.id", "runner_confirmations.owner_id"],
            ondelete="CASCADE",
            name="fk_runner_confirmation_inputs_confirmation_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    confirmation_id: Mapped[str] = mapped_column(Text, nullable=False)
    logical_path: Mapped[str] = mapped_column(Text, nullable=False)
    declared_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_content: Mapped[str] = mapped_column(Text, nullable=False)


class RunnerInputRow(Base):
    __tablename__ = "runner_inputs"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_runner_inputs_id_owner"),
        UniqueConstraint(
            "runner_id", "logical_path", name="uq_runner_inputs_runner_path"
        ),
        ForeignKeyConstraint(
            ["runner_id", "owner_id"],
            ["runner_records.id", "runner_records.owner_id"],
            ondelete="CASCADE",
            name="fk_runner_inputs_runner_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    runner_id: Mapped[str] = mapped_column(Text, nullable=False)
    logical_path: Mapped[str] = mapped_column(Text, nullable=False)
    declared_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)


class RunnerOutputChunkRow(Base):
    __tablename__ = "runner_output_chunks"
    __table_args__ = (
        CheckConstraint("phase IN ('compile','test','static')", name="phase_valid"),
        CheckConstraint("stream IN ('stdout','stderr')", name="stream_valid"),
        CheckConstraint("truncated IN (0,1)", name="truncated_valid"),
        UniqueConstraint("id", "owner_id", name="uq_runner_output_chunks_id_owner"),
        UniqueConstraint(
            "runner_id",
            "stream",
            "sequence",
            name="uq_runner_output_chunks_runner_stream_sequence",
        ),
        UniqueConstraint(
            "runner_id", "ordinal", name="uq_runner_output_chunks_runner_ordinal"
        ),
        ForeignKeyConstraint(
            ["runner_id", "owner_id"],
            ["runner_records.id", "runner_records.owner_id"],
            ondelete="CASCADE",
            name="fk_runner_chunks_runner_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    runner_id: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    stream: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content_ref: Mapped[str] = mapped_column(Text, nullable=False)
    truncated: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()

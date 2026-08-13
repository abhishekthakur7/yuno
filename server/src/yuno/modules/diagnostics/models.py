"""SQLAlchemy persistence models for diagnostic sessions and answers."""

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

from yuno.shared.infrastructure.base import (
    Base,
    boolean_column,
    id_column,
    row_version_column,
    utc_timestamp_column,
)


class DiagnosticSessionRow(Base):
    __tablename__ = "diagnostic_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["confirmed_goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_diagnostic_sessions_confirmed_goal_owner",
        ),
        CheckConstraint(
            "state IN ('not-started','in-progress','paused','resumed','skipped','roadmap-preview','failed','confirmed','expired')",
            name="state_valid",
        ),
        CheckConstraint(
            "untrusted_seed_kind IS NULL OR untrusted_seed_kind IN ('notes','questions')",
            name="untrusted_seed_kind_valid",
        ),
        CheckConstraint(
            "length(trim(question_set_version)) > 0",
            name="question_set_version_non_blank",
        ),
        UniqueConstraint("id", "owner_id", name="uq_diagnostic_sessions_id_owner"),
        Index(
            "ix_diagnostic_sessions_owner_state_recent",
            "owner_id",
            "state",
            "updated_at",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    captured_graph_version_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("editorial_approvals.graph_version_id"),
        nullable=False,
    )
    question_set_version: Mapped[str] = mapped_column(Text, nullable=False)
    setup_inputs_hash: Mapped[str | None] = mapped_column(Text)
    untrusted_seed_kind: Mapped[str | None] = mapped_column(Text)
    untrusted_seed_hash: Mapped[str | None] = mapped_column(Text)
    seed_skipped: Mapped[int] = boolean_column("seed_skipped", default=False)
    diagnostic_skipped: Mapped[int] = boolean_column(
        "diagnostic_skipped", default=False
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    paused_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    expires_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    failure_code: Mapped[str | None] = mapped_column(Text)
    failure_reference: Mapped[str | None] = mapped_column(Text)
    confirmed_goal_id: Mapped[str | None] = mapped_column(Text)
    row_version: Mapped[int] = row_version_column()
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class DiagnosticAnswerRow(Base):
    __tablename__ = "diagnostic_answers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "owner_id"],
            ["diagnostic_sessions.id", "diagnostic_sessions.owner_id"],
            name="fk_diagnostic_answers_session_owner",
        ),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
        CheckConstraint(
            "confidence IN ('low','medium','high')", name="confidence_valid"
        ),
        CheckConstraint(
            "length(trim(question_ref)) > 0", name="question_ref_non_blank"
        ),
        CheckConstraint(
            "length(trim(adaptive_context_version)) > 0",
            name="adaptive_context_version_non_blank",
        ),
        UniqueConstraint("id", "owner_id", name="uq_diagnostic_answers_id_owner"),
        UniqueConstraint(
            "session_id", "sequence", name="uq_diagnostic_answers_session_sequence"
        ),
        Index(
            "ix_diagnostic_answers_owner_session_sequence",
            "owner_id",
            "session_id",
            "sequence",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    question_ref: Mapped[str] = mapped_column(Text, nullable=False)
    answer_hash: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    adaptive_context_version: Mapped[str] = mapped_column(Text, nullable=False)
    answered_at: Mapped[str] = utc_timestamp_column()


class DiagnosticPreviewEditRow(Base):
    __tablename__ = "diagnostic_preview_edits"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "owner_id"],
            ["diagnostic_sessions.id", "diagnostic_sessions.owner_id"],
            name="fk_diagnostic_preview_edits_session_owner",
        ),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
        CheckConstraint(
            "entry_type IN ('order_constraint','skip','depth','correction')",
            name="entry_type_valid",
        ),
        UniqueConstraint("id", "owner_id", name="uq_diagnostic_preview_edits_id_owner"),
        UniqueConstraint(
            "session_id", "sequence", name="uq_diagnostic_preview_edits_sequence"
        ),
        Index(
            "ix_diagnostic_preview_edits_owner_session_sequence",
            "owner_id",
            "session_id",
            "sequence",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_stable_id: Mapped[str | None] = mapped_column(Text)
    entry_type: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = utc_timestamp_column()


class DiagnosticsCommandLockRow(Base):
    __tablename__ = "diagnostics_command_locks"

    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), primary_key=True
    )
    created_at: Mapped[str] = utc_timestamp_column()


class DiagnosticsIdempotencyRow(Base):
    __tablename__ = "diagnostics_idempotency"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "owner_id"],
            ["diagnostic_sessions.id", "diagnostic_sessions.owner_id"],
            name="fk_diagnostics_idempotency_session_owner",
        ),
        CheckConstraint("length(trim(operation)) > 0", name="operation_non_blank"),
        CheckConstraint(
            "length(trim(idempotency_key)) > 0", name="idempotency_key_non_blank"
        ),
        UniqueConstraint("id", "owner_id", name="uq_diagnostics_idempotency_id_owner"),
        UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_diagnostics_idempotency_command",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    response_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()

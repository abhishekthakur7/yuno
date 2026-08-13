"""SQLAlchemy persistence models for untrusted imports."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import (
    Base,
    id_column,
    row_version_column,
    utc_timestamp_column,
)


class ImportRecordRow(Base):
    __tablename__ = "import_records"
    __table_args__ = (
        CheckConstraint("type IN ('markdown','plain_text')", name="type_valid"),
        CheckConstraint(
            "status IN ('selected','parsing','parsed-untrusted','learner-review','applied','failed','cancelled')",
            name="status_valid",
        ),
        UniqueConstraint("id", "owner_id", name="uq_import_records_id_owner"),
        Index(
            "ix_import_records_owner_goal_created", "owner_id", "goal_id", "created_at"
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_import_records_goal_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    original_hash: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(Text)
    failure_reference: Mapped[str | None] = mapped_column(Text)
    row_version: Mapped[int] = row_version_column()
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class ImportStatementRow(Base):
    __tablename__ = "import_statements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["import_id", "owner_id"],
            ["import_records.id", "import_records.owner_id"],
            name="fk_import_statements_import_owner",
        ),
        ForeignKeyConstraint(
            ["duplicate_of_statement_id", "owner_id"],
            ["import_statements.id", "import_statements.owner_id"],
            name="fk_import_statements_duplicate_owner",
        ),
        UniqueConstraint("id", "owner_id", name="uq_import_statements_id_owner"),
        UniqueConstraint(
            "import_id",
            "parser_version",
            "sequence",
            name="uq_import_statements_occurrence",
        ),
        CheckConstraint("sequence > 0", name="sequence_positive"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "trust_state IN ('untrusted','verified','dismissed')",
            name="trust_state_valid",
        ),
        CheckConstraint(
            "mapping_state IN ('unmapped','mapped','duplicate')",
            name="mapping_state_valid",
        ),
        Index(
            "ix_import_statements_owner_import_sequence",
            "owner_id",
            "import_id",
            "parser_version",
            "sequence",
        ),
        Index(
            "uq_import_statements_unmapped_hash",
            "owner_id",
            "parser_version",
            "normalized_hash",
            unique=True,
            sqlite_where=text("mapping_state = 'unmapped'"),
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    import_id: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    original_hash: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_hash: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    duplicate_of_statement_id: Mapped[str | None] = mapped_column(Text)
    trust_state: Mapped[str] = mapped_column(Text, nullable=False)
    mapping_state: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_hash: Mapped[str | None] = mapped_column(Text)
    row_version: Mapped[int] = row_version_column()
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class ImportStatementDecisionRow(Base):
    __tablename__ = "import_statement_decisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["statement_id", "owner_id"],
            ["import_statements.id", "import_statements.owner_id"],
            name="fk_import_statement_decisions_statement_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", name="uq_import_statement_decisions_id_owner"
        ),
        CheckConstraint(
            "decision_type IN ('corrected','verified','dismissed')",
            name="decision_type_valid",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    statement_id: Mapped[str] = mapped_column(Text, nullable=False)
    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    value_hash: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[str] = utc_timestamp_column()


class ImportStatementMappingRow(Base):
    __tablename__ = "import_statement_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_import_statement_mappings_goal_owner",
        ),
        ForeignKeyConstraint(
            ["statement_id", "owner_id"],
            ["import_statements.id", "import_statements.owner_id"],
            name="fk_import_statement_mappings_statement_owner",
        ),
        ForeignKeyConstraint(
            ["graph_version_id", "topic_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_import_statement_mappings_topic",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_import_statement_mappings_id_owner_goal",
        ),
        CheckConstraint("decision IN ('approved','revoked')", name="decision_valid"),
        Index(
            "uq_import_statement_mappings_active",
            "owner_id",
            "statement_id",
            unique=True,
            sqlite_where=text("decision = 'approved' AND revoked_at IS NULL"),
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    statement_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str] = mapped_column(Text, nullable=False)
    graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("editorial_approvals.graph_version_id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_at: Mapped[str] = utc_timestamp_column()
    revoked_at: Mapped[str | None] = utc_timestamp_column(nullable=True)


class TopicImportHashRow(Base):
    __tablename__ = "topic_import_hashes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_topic_import_hashes_goal_owner",
        ),
        ForeignKeyConstraint(
            ["graph_version_id", "topic_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_topic_import_hashes_topic",
        ),
    )
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), primary_key=True
    )
    goal_id: Mapped[str] = mapped_column(Text, primary_key=True)
    graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("editorial_approvals.graph_version_id"), primary_key=True
    )
    topic_stable_id: Mapped[str] = mapped_column(Text, primary_key=True)
    imports_hash: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = utc_timestamp_column()


class ImportsIdempotencyRow(Base):
    __tablename__ = "imports_idempotency"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_imports_idempotency_id_owner"),
        UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_imports_idempotency_command",
        ),
        CheckConstraint("length(trim(operation)) > 0", name="operation_non_blank"),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    response_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()

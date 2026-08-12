"""SQLAlchemy source registry model."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import Base, id_column, utc_timestamp_column


class SourceRow(Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_sources_id_owner"),
        CheckConstraint("length(trim(origin)) > 0", name="origin_non_blank"),
        CheckConstraint("length(trim(source_type)) > 0", name="source_type_non_blank"),
        CheckConstraint("length(trim(title)) > 0", name="title_non_blank"),
        CheckConstraint(
            "length(trim(license_status)) > 0", name="license_status_non_blank"
        ),
        CheckConstraint(
            "availability_status IN ('available','unavailable','withdrawn')",
            name="availability_status_valid",
        ),
        Index(
            "ix_sources_owner_availability_title",
            "owner_id",
            "availability_status",
            "title",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    license_status: Mapped[str] = mapped_column(Text, nullable=False)
    availability_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class SourceSnapshotRow(Base):
    __tablename__ = "source_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_id", "owner_id"],
            ["sources.id", "sources.owner_id"],
            name="fk_source_snapshots_source_owner",
        ),
        UniqueConstraint("id", "owner_id", name="uq_source_snapshots_id_owner"),
        UniqueConstraint(
            "id", "owner_id", "source_id", name="uq_source_snapshots_id_owner_source"
        ),
        CheckConstraint(
            "status IN ('available','unavailable','withdrawn','failed')",
            name="status_valid",
        ),
        CheckConstraint("length(trim(content_ref)) > 0", name="content_ref_non_blank"),
        CheckConstraint(
            "length(trim(content_hash)) > 0", name="content_hash_non_blank"
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[str] = utc_timestamp_column()
    content_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    version_label: Mapped[str | None] = mapped_column(Text)
    redacted_failure: Mapped[str | None] = mapped_column(Text)


class SourceRetrievalCommandRow(Base):
    __tablename__ = "source_retrieval_commands"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_id", "owner_id"],
            ["sources.id", "sources.owner_id"],
            name="fk_source_retrieval_commands_source_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", name="uq_source_retrieval_commands_id_owner"
        ),
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_source_retrieval_commands_idempotency",
        ),
        UniqueConstraint("job_id", name="uq_source_retrieval_commands_job"),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class ArtifactProvenanceSnapshotRow(Base):
    __tablename__ = "artifact_provenance_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "generated_artifacts.id",
                "generated_artifacts.owner_id",
                "generated_artifacts.goal_id",
            ],
            name="fk_artifact_provenance_snapshots_artifact_owner_goal",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_artifact_provenance_snapshots_id_owner_goal",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            "artifact_id",
            name="uq_artifact_provenance_snapshots_id_owner_goal_artifact",
        ),
        UniqueConstraint("attempt_id", name="uq_artifact_provenance_snapshots_attempt"),
        ForeignKeyConstraint(
            ["attempt_id", "owner_id", "goal_id", "artifact_id"],
            [
                "artifact_generation_attempts.id",
                "artifact_generation_attempts.owner_id",
                "artifact_generation_attempts.goal_id",
                "artifact_generation_attempts.artifact_id",
            ],
            name="fk_artifact_provenance_snapshots_attempt_owner_goal_artifact",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_id: Mapped[str] = mapped_column(
        Text, ForeignKey("artifact_generation_attempts.id"), nullable=False
    )
    evidence_state_hash: Mapped[str] = mapped_column(Text, nullable=False)
    profile_hash: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[str] = utc_timestamp_column()
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    contract_version: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False)


class ArtifactProvenanceRefRow(Base):
    __tablename__ = "artifact_provenance_refs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["snapshot_id", "owner_id", "goal_id", "artifact_id"],
            [
                "artifact_provenance_snapshots.id",
                "artifact_provenance_snapshots.owner_id",
                "artifact_provenance_snapshots.goal_id",
                "artifact_provenance_snapshots.artifact_id",
            ],
            name="fk_artifact_provenance_refs_snapshot_owner_goal_artifact",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_artifact_provenance_refs_id_owner_goal",
        ),
        UniqueConstraint(
            "snapshot_id",
            "ref_kind",
            "reference_id",
            name="uq_artifact_provenance_refs_ref",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_id: Mapped[str] = mapped_column(Text, nullable=False)
    ref_kind: Mapped[str] = mapped_column(Text, nullable=False)
    reference_id: Mapped[str] = mapped_column(Text, nullable=False)


class ClaimRow(Base):
    __tablename__ = "claims"
    __table_args__ = (
        ForeignKeyConstraint(
            ["generated_artifact_id", "owner_id", "goal_id"],
            [
                "generated_artifacts.id",
                "generated_artifacts.owner_id",
                "generated_artifacts.goal_id",
            ],
            name="fk_claims_artifact_owner_goal",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "owner_id", "goal_id", "generated_artifact_id"],
            [
                "artifact_provenance_snapshots.id",
                "artifact_provenance_snapshots.owner_id",
                "artifact_provenance_snapshots.goal_id",
                "artifact_provenance_snapshots.artifact_id",
            ],
            name="fk_claims_snapshot_owner_goal_artifact",
        ),
        ForeignKeyConstraint(
            ["content_revision_id"],
            ["content_revisions.id"],
            name="fk_claims_content_revision",
        ),
        UniqueConstraint("id", "owner_id", name="uq_claims_id_owner"),
        CheckConstraint(
            "claim_type IN ('fact','trade-off','routine','disputed','comparative','time-or-version-dependent')",
            name="claim_type_valid",
        ),
        CheckConstraint("status IN ('pending','published')", name="status_valid"),
        CheckConstraint(
            "(content_revision_id IS NOT NULL) != (generated_artifact_id IS NOT NULL)",
            name="exactly_one_parent",
        ),
        CheckConstraint(
            "generated_artifact_id IS NOT NULL OR snapshot_id IS NULL",
            name="snapshot_generated_only",
        ),
        CheckConstraint("sensitive IN (0,1)", name="sensitive_in_0_1"),
        CheckConstraint("length(trim(claim_text)) > 0", name="claim_text_non_blank"),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str | None] = mapped_column(Text)
    content_revision_id: Mapped[str | None] = mapped_column(Text)
    generated_artifact_id: Mapped[str | None] = mapped_column(Text)
    snapshot_id: Mapped[str | None] = mapped_column(Text)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(Text, nullable=False)
    sensitive: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)


class CitationRow(Base):
    __tablename__ = "citations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_citations_goal_owner",
        ),
        ForeignKeyConstraint(
            ["claim_id", "owner_id"],
            ["claims.id", "claims.owner_id"],
            name="fk_citations_claim_owner",
        ),
        ForeignKeyConstraint(
            ["source_id", "owner_id"],
            ["sources.id", "sources.owner_id"],
            name="fk_citations_source_owner",
        ),
        ForeignKeyConstraint(
            ["source_snapshot_id", "owner_id", "source_id"],
            [
                "source_snapshots.id",
                "source_snapshots.owner_id",
                "source_snapshots.source_id",
            ],
            name="fk_citations_source_snapshot_owner_source",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_citations_id_owner_goal"
        ),
        UniqueConstraint(
            "claim_id",
            "source_id",
            "source_snapshot_id",
            "locator",
            name="uq_citations_support",
        ),
        CheckConstraint("length(trim(locator)) > 0", name="locator_non_blank"),
        CheckConstraint(
            "length(trim(support_kind)) > 0", name="support_kind_non_blank"
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    claim_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_snapshot_id: Mapped[str | None] = mapped_column(Text)
    locator: Mapped[str] = mapped_column(Text, nullable=False)
    support_kind: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

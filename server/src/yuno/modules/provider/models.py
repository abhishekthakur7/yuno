"""Provider disclosure, request diagnostic, and quarantine persistence."""

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


class NetworkDisclosureRow(Base):
    __tablename__ = "network_disclosures"
    __table_args__ = (
        CheckConstraint("length(trim(category)) > 0", name="category_valid"),
        CheckConstraint(
            "json_valid(data_categories_json)", name="data_categories_json_valid"
        ),
        UniqueConstraint(
            "owner_id",
            "category",
            "disclosure_version",
            name="uq_network_disclosure_version",
        ),
        UniqueConstraint("id", "owner_id", name="uq_network_disclosures_id_owner"),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    data_categories_json: Mapped[str] = mapped_column(Text, nullable=False)
    disclosure_version: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_at: Mapped[str] = utc_timestamp_column()
    revoked_at: Mapped[str | None] = utc_timestamp_column(nullable=True)


class ProviderRequestRow(Base):
    __tablename__ = "provider_requests"
    __table_args__ = (
        CheckConstraint("provider IN ('codex','claude')", name="provider_valid"),
        CheckConstraint(
            "lifecycle IN ('preparing','running','succeeded','failed','quarantined','cancelled')",
            name="lifecycle_valid",
        ),
        UniqueConstraint("id", "owner_id", name="uq_provider_requests_id_owner"),
        ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            name="fk_provider_requests_job_owner",
        ),
        ForeignKeyConstraint(
            ["disclosure_id", "owner_id"],
            ["network_disclosures.id", "network_disclosures.owner_id"],
            name="fk_provider_requests_disclosure_owner",
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_provider_requests_goal_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    goal_id: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_version: Mapped[str] = mapped_column(Text, nullable=False)
    contract_version: Mapped[str] = mapped_column(Text, nullable=False)
    context_ref_hash: Mapped[str] = mapped_column(Text, nullable=False)
    disclosure_id: Mapped[str] = mapped_column(Text, nullable=False)
    pid: Mapped[int | None] = mapped_column(Integer)
    pgid: Mapped[int | None] = mapped_column(Integer)
    process_identity: Mapped[str | None] = mapped_column(Text)
    temp_path: Mapped[str | None] = mapped_column(Text)
    lifecycle: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostic_classification: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = utc_timestamp_column()
    started_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    completed_at: Mapped[str | None] = utc_timestamp_column(nullable=True)


class SchemaQuarantineRow(Base):
    __tablename__ = "schema_quarantines"
    __table_args__ = (
        CheckConstraint(
            "json_valid(validation_errors_json)", name="validation_errors_json_valid"
        ),
        UniqueConstraint("id", "owner_id", name="uq_schema_quarantines_id_owner"),
        ForeignKeyConstraint(
            ["provider_request_id", "owner_id"],
            ["provider_requests.id", "provider_requests.owner_id"],
            name="fk_schema_quarantine_request_owner",
        ),
        ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            name="fk_schema_quarantine_job_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    provider_request_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output_ref: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expected_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    validation_errors_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()

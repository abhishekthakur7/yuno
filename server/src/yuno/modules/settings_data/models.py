from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import (
    Base,
    row_version_column,
    utc_timestamp_column,
)


class OwnerSettingsRow(Base):
    __tablename__ = "owner_settings"
    __table_args__ = (
        CheckConstraint(
            "progress_display IN ('detailed','simple')",
            name="progress_display_valid",
        ),
        CheckConstraint(
            "json_valid(accessibility_json) AND json_type(accessibility_json)='object'",
            name="accessibility_json_valid",
        ),
        CheckConstraint(
            "provider_selection IS NULL OR provider_selection IN ('codex','claude')",
            name="provider_selection_valid",
        ),
    )

    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), primary_key=True
    )
    progress_display: Mapped[str] = mapped_column(
        Text, nullable=False, default="detailed", server_default="detailed"
    )
    accessibility_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default='{"reduced_motion":false}',
        server_default='{"reduced_motion":false}',
    )
    provider_selection: Mapped[str | None] = mapped_column(Text)
    row_version: Mapped[int] = row_version_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class ExportOperationRow(Base):
    __tablename__ = "export_operations"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_export_operations_id_owner"),
        CheckConstraint(
            "status IN ('queued','running','complete','failed','expired')",
            name="status_valid",
        ),
        CheckConstraint(
            "length(trim(format_version)) > 0", name="format_version_non_blank"
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"]
        ),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    format_version: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str | None] = mapped_column(Text)
    package_hash: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[str | None] = mapped_column(Text)
    result_ref: Mapped[str | None] = mapped_column(Text)
    failure_reference: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    package_expires_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    metadata_expires_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class DeleteOperationRow(Base):
    __tablename__ = "delete_operations"
    __table_args__ = (
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_delete_operations_id_owner_goal"
        ),
        CheckConstraint(
            "status IN ('preflight','queued','running','complete','failed')",
            name="status_valid",
        ),
        CheckConstraint(
            "json_valid(impact_json) AND json_type(impact_json)='object'",
            name="impact_json_valid",
        ),
        CheckConstraint("scope IN ('goal')", name="scope_valid"),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"]
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "owner_id", "goal_id"],
            [
                "evidence_delete_snapshots.id",
                "evidence_delete_snapshots.owner_id",
                "evidence_delete_snapshots.goal_id",
            ],
            name="fk_delete_operations_snapshot_owner_goal",
        ),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_id: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    impact_json: Mapped[str] = mapped_column(Text, nullable=False)
    impact_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[str | None] = mapped_column(Text)
    result_ref: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    failure_reference: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()

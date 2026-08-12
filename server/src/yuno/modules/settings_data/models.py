"""SQLAlchemy persistence for durable owner progress-display settings."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Text
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
    )

    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), primary_key=True
    )
    progress_display: Mapped[str] = mapped_column(
        Text, nullable=False, default="detailed", server_default="detailed"
    )
    row_version: Mapped[int] = row_version_column()
    updated_at: Mapped[str] = utc_timestamp_column()

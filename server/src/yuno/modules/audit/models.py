"""Append-only `audit_events` ORM model (spec §4.7, §4.1).

The append-only guarantee (rejecting UPDATE/DELETE) is enforced by SQLite
triggers owned by the Alembic migrations, not by this module.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import Base, id_column, utc_timestamp_column


class AuditEventRow(Base):
    """`audit_events` -- one row per `domain.AuditEvent`."""

    __tablename__ = "audit_events"
    __table_args__ = (
        # Composite UNIQUE(id, owner_id): spec §4.1's cross-owner-reference guard.
        UniqueConstraint("id", "owner_id"),
        Index("ix_audit_events_owner_occurred", "owner_id", "occurred_at"),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_role: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    before_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[str] = utc_timestamp_column()

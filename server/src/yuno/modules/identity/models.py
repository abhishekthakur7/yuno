"""Owner identity ORM models (spec §4.2)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import Base, id_column, utc_timestamp_column


class OwnerRow(Base):
    """`owners` -- singleton MVP owner row(s); never authenticated."""

    __tablename__ = "owners"
    __table_args__ = (
        CheckConstraint("kind IN ('local_builtin')", name="kind_valid"),
        CheckConstraint("status IN ('active','tombstoned')", name="status_valid"),
    )

    id: Mapped[str] = id_column()
    kind: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class OwnerRoleGrantRow(Base):
    """`owner_role_grants` -- D1 keeps learner/editor roles distinct."""

    __tablename__ = "owner_role_grants"
    __table_args__ = (
        CheckConstraint(
            "role IN ('learner','designated_editorial_approver')", name="role_valid"
        ),
    )

    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(Text, primary_key=True)
    assigned_at: Mapped[str] = utc_timestamp_column()
    assigned_by_owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False
    )

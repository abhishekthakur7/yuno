"""Evidence persistence models."""

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

from yuno.shared.infrastructure.base import Base, utc_timestamp_column


class EvidenceRow(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_evidence_goal_owner",
        ),
        UniqueConstraint("id", "owner_id", "goal_id", name="uq_evidence_id_owner_goal"),
        CheckConstraint(
            "length(trim(evidence_type)) > 0", name="evidence_type_non_blank"
        ),
        CheckConstraint(
            "capability IN ('know','understand','choose','implement','diagnose','defend')",
            name="capability_valid",
        ),
        CheckConstraint(
            "length(trim(payload_hash)) > 0", name="payload_hash_non_blank"
        ),
        CheckConstraint("length(trim(origin)) > 0", name="origin_non_blank"),
        Index(
            "ix_evidence_owner_goal_topic_created",
            "owner_id",
            "goal_id",
            "topic_stable_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str] = mapped_column(
        Text, ForeignKey("topic_identities.stable_id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class EvidencePayloadRow(Base):
    __tablename__ = "evidence_payloads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_evidence_payloads_evidence_owner_goal",
        ),
        UniqueConstraint(
            "evidence_id",
            "owner_id",
            "goal_id",
            name="uq_evidence_payloads_evidence_owner_goal",
        ),
        CheckConstraint(
            "length(trim(content_version)) > 0", name="content_version_non_blank"
        ),
    )

    evidence_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_version: Mapped[str] = mapped_column(Text, nullable=False)


class EvidenceTombstoneRow(Base):
    __tablename__ = "evidence_tombstones"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_evidence_tombstones_evidence_owner_goal",
        ),
        UniqueConstraint(
            "evidence_id",
            "owner_id",
            "goal_id",
            name="uq_evidence_tombstones_evidence_owner_goal",
        ),
        CheckConstraint(
            "length(trim(delete_operation_id)) > 0",
            name="delete_operation_id_non_blank",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="reason_non_blank"),
    )

    evidence_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    delete_operation_id: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    tombstoned_at: Mapped[str] = utc_timestamp_column()


class EvidenceDeleteSnapshotRow(Base):
    __tablename__ = "evidence_delete_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_evidence_delete_snapshots_goal_owner",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_evidence_delete_snapshots_id_owner_goal",
        ),
        CheckConstraint("json_valid(impact_json)", name="impact_json_valid"),
        CheckConstraint("json_type(impact_json) = 'object'", name="impact_json_object"),
        CheckConstraint("length(trim(impact_hash)) > 0", name="impact_hash_non_blank"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    impact_json: Mapped[str] = mapped_column(Text, nullable=False)
    impact_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()

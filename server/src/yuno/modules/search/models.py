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


class SearchDocumentRow(Base):
    __tablename__ = "search_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_search_documents_goal_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_search_documents_id_owner_goal"
        ),
        UniqueConstraint(
            "owner_id",
            "goal_id",
            "generation",
            "entity_type",
            "entity_id",
            name="uq_search_documents_projection_entity",
        ),
        CheckConstraint(
            "entity_type IN ('canonical-topic','canonical-content','generated-artifact','notebook-entry','evidence')",
            name="entity_type_valid",
        ),
        Index(
            "ix_search_documents_acl_generation",
            "owner_id",
            "goal_id",
            "generation",
            "entity_type",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    generation: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False)
    projection_version: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = utc_timestamp_column()


class SearchIndexStateRow(Base):
    __tablename__ = "search_index_state"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_search_index_state_id_owner"),
        UniqueConstraint(
            "owner_id", "projection_name", name="uq_search_index_state_owner_projection"
        ),
        CheckConstraint(
            "status IN ('ready','stale','rebuilding','failed','unavailable')",
            name="status_valid",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    projection_name: Mapped[str] = mapped_column(Text, nullable=False)
    active_generation: Mapped[str | None] = mapped_column(Text)
    projection_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source_watermark: Mapped[str] = mapped_column(Text, nullable=False)
    rebuild_job_id: Mapped[str | None] = mapped_column(Text)
    failure_reference: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()

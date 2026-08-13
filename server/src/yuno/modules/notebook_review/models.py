"""SQLAlchemy persistence for notebooks and review queues."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yuno.shared.infrastructure.base import (
    Base,
    boolean_column,
    id_column,
    row_version_column,
    utc_timestamp_column,
)


class NotebookEntryRow(Base):
    __tablename__ = "notebook_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_notebook_entries_goal_owner",
        ),
        ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_notebook_entries_evidence_owner_goal",
        ),
        ForeignKeyConstraint(
            ["source_id", "owner_id"],
            ["sources.id", "sources.owner_id"],
            name="fk_notebook_entries_source_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_notebook_entries_id_owner_goal"
        ),
        CheckConstraint("entry_kind IN ('auto','user')", name="entry_kind_valid"),
        Index(
            "ix_notebook_entries_owner_goal_tombstone_updated",
            "owner_id",
            "goal_id",
            "tombstoned_at",
            "updated_at",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("topic_identities.stable_id")
    )
    evidence_id: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(Text)
    entry_kind: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    row_version: Mapped[int] = row_version_column()
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()
    tombstoned_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    body: Mapped[NotebookEntryBodyRow | None] = relationship(
        cascade="all, delete-orphan", lazy="joined", uselist=False
    )


class GoalReviewPreferencesRow(Base):
    __tablename__ = "goal_review_preferences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_goal_review_preferences_goal_owner",
        ),
        UniqueConstraint(
            "goal_id", "owner_id", name="uq_goal_review_preferences_goal_owner"
        ),
        CheckConstraint(
            "duration_minutes IN (10,15,25)", name="duration_minutes_valid"
        ),
        CheckConstraint(
            "cadence IN ('once-weekly','twice-weekly','three-times-weekly')",
            name="cadence_valid",
        ),
        CheckConstraint(
            "length(trim(scheduling_version)) > 0", name="scheduling_version_non_blank"
        ),
    )
    goal_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    enabled: Mapped[int] = boolean_column("enabled", default=True)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)
    cadence: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_enabled: Mapped[int] = boolean_column("retrieval_enabled", default=True)
    varied_context_enabled: Mapped[int] = boolean_column(
        "varied_context_enabled", default=True
    )
    scheduling_version: Mapped[str] = mapped_column(Text, nullable=False)
    row_version: Mapped[int] = row_version_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class ReviewItemRow(Base):
    __tablename__ = "review_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_review_items_goal_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_review_items_id_owner_goal"
        ),
        CheckConstraint(
            "prompt_type IN ('recall','explanation','application')",
            name="prompt_type_valid",
        ),
        CheckConstraint(
            "status IN ('ready','due','dismissed','disabled','generation-failed','completed')",
            name="status_valid",
        ),
        CheckConstraint("length(trim(prompt_ref)) > 0", name="prompt_ref_non_blank"),
        CheckConstraint(
            "length(trim(scheduling_version)) > 0", name="scheduling_version_non_blank"
        ),
        CheckConstraint(
            "status != 'due' OR due_at IS NOT NULL", name="due_has_timestamp"
        ),
        CheckConstraint(
            "status != 'generation-failed' OR failure_reference IS NOT NULL",
            name="failure_has_reference",
        ),
        Index(
            "ix_review_items_owner_goal_status_due",
            "owner_id",
            "goal_id",
            "status",
            "due_at",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str] = mapped_column(
        Text, ForeignKey("topic_identities.stable_id"), nullable=False
    )
    prompt_ref: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_type: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    interval_label: Mapped[str | None] = mapped_column(Text)
    scheduling_version: Mapped[str] = mapped_column(Text, nullable=False)
    failure_reference: Mapped[str | None] = mapped_column(Text)
    row_version: Mapped[int] = row_version_column()
    created_at: Mapped[str] = utc_timestamp_column()
    body: Mapped[ReviewItemBodyRow | None] = relationship(
        cascade="all, delete-orphan", lazy="joined", uselist=False
    )
    updated_at: Mapped[str] = utc_timestamp_column()


class ReviewAttemptRow(Base):
    __tablename__ = "review_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_review_attempts_goal_owner",
        ),
        ForeignKeyConstraint(
            ["review_item_id", "owner_id", "goal_id"],
            ["review_items.id", "review_items.owner_id", "review_items.goal_id"],
            name="fk_review_attempts_item_owner_goal",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_review_attempts_id_owner_goal"
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence IN ('low','medium','high')",
            name="confidence_valid",
        ),
        CheckConstraint(
            "length(trim(scheduling_version)) > 0", name="scheduling_version_non_blank"
        ),
        Index(
            "ix_review_attempts_owner_goal_item_created",
            "owner_id",
            "goal_id",
            "review_item_id",
            "created_at",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    review_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str | None] = mapped_column(Text)
    next_interval_label: Mapped[str | None] = mapped_column(Text)
    scheduling_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()
    body: Mapped[ReviewAttemptBodyRow | None] = relationship(
        cascade="all, delete-orphan", lazy="joined", uselist=False
    )


class NotebookEntryBodyRow(Base):
    __tablename__ = "notebook_entry_bodies"
    entry_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["entry_id", "owner_id", "goal_id"],
            [
                "notebook_entries.id",
                "notebook_entries.owner_id",
                "notebook_entries.goal_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("length(trim(markdown)) > 0", name="markdown_non_blank"),
    )


class ReviewItemBodyRow(Base):
    __tablename__ = "review_item_bodies"
    review_item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_item_id", "owner_id", "goal_id"],
            ["review_items.id", "review_items.owner_id", "review_items.goal_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("length(trim(prompt)) > 0", name="prompt_non_blank"),
        CheckConstraint(
            "answer IS NULL OR length(trim(answer)) > 0", name="answer_non_blank"
        ),
    )


class ReviewAttemptBodyRow(Base):
    __tablename__ = "review_attempt_bodies"
    attempt_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text)
    correction: Mapped[str | None] = mapped_column(Text)
    context_variation: Mapped[str | None] = mapped_column(Text)
    context_result: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "owner_id", "goal_id"],
            [
                "review_attempts.id",
                "review_attempts.owner_id",
                "review_attempts.goal_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("length(trim(response)) > 0", name="response_non_blank"),
    )


class NotebookReviewIdempotencyRow(Base):
    __tablename__ = "notebook_review_idempotency"
    __table_args__ = (
        UniqueConstraint(
            "id", "owner_id", name="uq_notebook_review_idempotency_id_owner"
        ),
        UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_notebook_review_idempotency_command",
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

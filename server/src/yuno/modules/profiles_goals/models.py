"""SQLAlchemy persistence models for profiles and goal workspaces."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import Base, id_column, utc_timestamp_column


class GoalWorkspaceRow(Base):
    __tablename__ = "goal_workspaces"
    __table_args__ = (
        CheckConstraint("path IN ('learn','interview_prep')", name="path_valid"),
        CheckConstraint(
            "target_level IN ('Mid-level','Senior','Staff')", name="target_level_valid"
        ),
        CheckConstraint(
            "target_capability IN ('know','understand','choose','implement','diagnose','defend')",
            name="target_capability_valid",
        ),
        CheckConstraint(
            "status IN ('active','archived','tombstoned')", name="status_valid"
        ),
        CheckConstraint("length(trim(name)) > 0", name="name_non_blank"),
        CheckConstraint(
            "path != 'learn' OR length(trim(subject)) > 0",
            name="learn_subject_required",
        ),
        CheckConstraint(
            "path != 'interview_prep' OR length(trim(role)) > 0",
            name="interview_role_required",
        ),
        CheckConstraint("path != 'learn' OR role IS NULL", name="learn_role_absent"),
        CheckConstraint(
            "path != 'interview_prep' OR subject IS NULL",
            name="interview_subject_absent",
        ),
        UniqueConstraint("id", "owner_id", name="uq_goal_workspaces_id_owner"),
        Index(
            "ix_goal_workspaces_owner_status_recent",
            "owner_id",
            "status",
            "last_accessed_at",
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    target_level: Mapped[str] = mapped_column(Text, nullable=False)
    target_capability: Mapped[str] = mapped_column(Text, nullable=False)
    graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_graph_versions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    resume_position: Mapped[str | None] = mapped_column(Text)
    last_accessed_at: Mapped[str | None] = mapped_column(Text)
    row_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()


class LearnerProfileRow(Base):
    __tablename__ = "learner_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["current_goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_learner_profiles_current_goal_owner",
        ),
    )

    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), primary_key=True
    )
    experience: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[str | None] = mapped_column(Text)
    weaknesses: Mapped[str | None] = mapped_column(Text)
    current_goal_id: Mapped[str | None] = mapped_column(Text)
    profile_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    updated_at: Mapped[str] = utc_timestamp_column()


class GoalNavigationEventRow(Base):
    __tablename__ = "goal_navigation_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_goal_navigation_events_goal_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_goal_navigation_events_id_owner_goal"
        ),
        CheckConstraint(
            "destination IN ('/app/learn-roadmap','/app/topic-studio','/app/interview-hub','/app/practice','/app/mock')",
            name="destination_valid",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[str | None] = mapped_column(Text)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[str] = utc_timestamp_column()


class RecommendationDismissalRow(Base):
    __tablename__ = "recommendation_dismissals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_recommendation_dismissals_goal_owner",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_recommendation_dismissals_id_owner_goal",
        ),
        UniqueConstraint(
            "owner_id",
            "goal_id",
            "recommendation_key",
            name="uq_recommendation_dismissal_key",
        ),
        CheckConstraint(
            "length(trim(recommendation_key)) > 0", name="recommendation_key_non_blank"
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation_key: Mapped[str] = mapped_column(Text, nullable=False)
    dismissed_at: Mapped[str] = utc_timestamp_column()


class ProfilesGoalsIdempotencyRow(Base):
    __tablename__ = "profiles_goals_idempotency"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_profiles_goals_idempotency_goal_owner",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_profiles_goals_idempotency_id_owner_goal",
        ),
        UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_profiles_goals_idempotency_command",
        ),
        CheckConstraint("length(trim(operation)) > 0", name="operation_non_blank"),
        CheckConstraint(
            "length(trim(idempotency_key)) > 0", name="idempotency_key_non_blank"
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()

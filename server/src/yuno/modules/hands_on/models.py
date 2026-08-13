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

from yuno.shared.infrastructure.base import Base, utc_timestamp_column


class HandsOnWorkRow(Base):
    __tablename__ = "hands_on_work"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_hands_on_work_goal_owner",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_hands_on_work_id_owner_goal"
        ),
        UniqueConstraint(
            "owner_id", "goal_id", "topic_stable_id", name="uq_hands_on_work_topic"
        ),
        CheckConstraint(
            "scenario_status IN ('fixture')", name="hands_on_scenario_status_valid"
        ),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_stable_id: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_status: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class HandsOnWorkBodyRow(Base):
    __tablename__ = "hands_on_work_bodies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["work_id", "owner_id", "goal_id"],
            ["hands_on_work.id", "hands_on_work.owner_id", "hands_on_work.goal_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "length(trim(role)) > 0", name="hands_on_work_bodies_role_non_blank"
        ),
        CheckConstraint(
            "length(trim(scenario_title)) > 0",
            name="hands_on_scenario_title_non_blank",
        ),
        CheckConstraint(
            "length(trim(scenario_prompt)) > 0",
            name="hands_on_scenario_prompt_non_blank",
        ),
        CheckConstraint("length(trim(level)) > 0", name="hands_on_level_non_blank"),
        CheckConstraint(
            "json_valid(constraints_json) AND json_type(constraints_json) = 'array'",
            name="hands_on_constraints_array",
        ),
        CheckConstraint(
            "length(trim(scenario_source)) > 0",
            name="hands_on_scenario_source_non_blank",
        ),
    )

    work_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_title: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    constraints_json: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_source: Mapped[str] = mapped_column(Text, nullable=False)


class HandsOnArtifactRow(Base):
    __tablename__ = "hands_on_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["work_id", "owner_id", "goal_id"],
            ["hands_on_work.id", "hands_on_work.owner_id", "hands_on_work.goal_id"],
            name="fk_hands_on_artifacts_work",
        ),
        ForeignKeyConstraint(
            ["evidence_id", "owner_id", "goal_id"],
            ["evidence.id", "evidence.owner_id", "evidence.goal_id"],
            name="fk_hands_on_artifacts_evidence",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_hands_on_artifacts_id_owner_goal"
        ),
        UniqueConstraint(
            "work_id", "revision_number", name="uq_hands_on_artifacts_revision"
        ),
        CheckConstraint("revision_number > 0", name="hands_on_revision_positive"),
        CheckConstraint(
            "length(trim(content_hash)) > 0", name="hands_on_artifact_hash_non_blank"
        ),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    work_id: Mapped[str] = mapped_column(Text, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    response_to_question_id: Mapped[str | None] = mapped_column(Text)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class HandsOnArtifactBodyRow(Base):
    __tablename__ = "hands_on_artifact_bodies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "hands_on_artifacts.id",
                "hands_on_artifacts.owner_id",
                "hands_on_artifacts.goal_id",
            ],
            ondelete="CASCADE",
        ),
    )

    artifact_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    cross_question_response: Mapped[str | None] = mapped_column(Text)


class HandsOnReviewRow(Base):
    __tablename__ = "hands_on_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "hands_on_artifacts.id",
                "hands_on_artifacts.owner_id",
                "hands_on_artifacts.goal_id",
            ],
            name="fk_hands_on_reviews_artifact",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_hands_on_reviews_id_owner_goal"
        ),
        UniqueConstraint("artifact_id", name="uq_hands_on_reviews_artifact"),
        CheckConstraint("review_mode IN ('static')", name="hands_on_review_mode_valid"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    work_id: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_id: Mapped[str] = mapped_column(Text, nullable=False)
    review_mode: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class HandsOnReviewBodyRow(Base):
    __tablename__ = "hands_on_review_bodies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "owner_id", "goal_id"],
            [
                "hands_on_reviews.id",
                "hands_on_reviews.owner_id",
                "hands_on_reviews.goal_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "length(trim(required_limitation_label)) > 0",
            name="hands_on_static_limitation_non_blank",
        ),
    )

    review_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    required_limitation_label: Mapped[str] = mapped_column(Text, nullable=False)


class HandsOnCrossQuestionRow(Base):
    __tablename__ = "hands_on_cross_questions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "hands_on_artifacts.id",
                "hands_on_artifacts.owner_id",
                "hands_on_artifacts.goal_id",
            ],
            name="fk_hands_on_questions_artifact",
        ),
        ForeignKeyConstraint(
            ["review_id", "owner_id", "goal_id"],
            [
                "hands_on_reviews.id",
                "hands_on_reviews.owner_id",
                "hands_on_reviews.goal_id",
            ],
            name="fk_hands_on_questions_review",
        ),
        UniqueConstraint(
            "id", "owner_id", "goal_id", name="uq_hands_on_questions_id_owner_goal"
        ),
        UniqueConstraint("review_id", name="uq_hands_on_questions_review"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    work_id: Mapped[str] = mapped_column(Text, nullable=False)
    review_id: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class HandsOnCrossQuestionBodyRow(Base):
    __tablename__ = "hands_on_cross_question_bodies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["question_id", "owner_id", "goal_id"],
            [
                "hands_on_cross_questions.id",
                "hands_on_cross_questions.owner_id",
                "hands_on_cross_questions.goal_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "length(trim(question)) > 0", name="hands_on_question_non_blank"
        ),
        CheckConstraint(
            "length(trim(target_gap)) > 0", name="hands_on_target_gap_non_blank"
        ),
    )

    question_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    target_gap: Mapped[str] = mapped_column(Text, nullable=False)

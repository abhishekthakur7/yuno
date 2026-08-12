from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from yuno.modules.hands_on.domain import (
    HandsOnArtifact,
    HandsOnCrossQuestion,
    HandsOnReview,
    HandsOnWork,
    ReviewMode,
)
from yuno.modules.hands_on.models import (
    HandsOnArtifactRow,
    HandsOnCrossQuestionRow,
    HandsOnReviewRow,
    HandsOnWorkRow,
)


class SqlAlchemyHandsOnRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_work(self, owner_id, goal_id, topic_id):
        row = self._session.scalar(
            select(HandsOnWorkRow).where(
                HandsOnWorkRow.owner_id == owner_id,
                HandsOnWorkRow.goal_id == goal_id,
                HandsOnWorkRow.topic_stable_id == topic_id,
            )
        )
        return _work(row) if row else None

    def add_work(self, work):
        values = work.__dict__.copy()
        values["constraints_json"] = json.dumps(values.pop("constraints"))
        self._session.add(HandsOnWorkRow(**values))
        self._session.flush()
        return work

    def list_artifacts(self, owner_id, work_id):
        rows = self._session.scalars(
            select(HandsOnArtifactRow)
            .where(
                HandsOnArtifactRow.owner_id == owner_id,
                HandsOnArtifactRow.work_id == work_id,
            )
            .order_by(HandsOnArtifactRow.revision_number)
        ).all()
        return tuple(_artifact(row) for row in rows)

    def get_artifact(self, owner_id, artifact_id):
        row = self._session.scalar(
            select(HandsOnArtifactRow).where(
                HandsOnArtifactRow.owner_id == owner_id,
                HandsOnArtifactRow.id == artifact_id,
            )
        )
        return _artifact(row) if row else None

    def get_artifact_by_evidence(self, owner_id, evidence_id):
        row = self._session.scalar(
            select(HandsOnArtifactRow).where(
                HandsOnArtifactRow.owner_id == owner_id,
                HandsOnArtifactRow.evidence_id == evidence_id,
            )
        )
        return _artifact(row) if row else None

    def add_artifact(self, artifact):
        self._session.add(HandsOnArtifactRow(**artifact.__dict__))
        self._session.flush()
        return artifact

    def get_question(self, owner_id, question_id):
        row = self._session.scalar(
            select(HandsOnCrossQuestionRow).where(
                HandsOnCrossQuestionRow.owner_id == owner_id,
                HandsOnCrossQuestionRow.id == question_id,
            )
        )
        return _question(row) if row else None

    def list_reviews(self, owner_id, work_id):
        rows = self._session.scalars(
            select(HandsOnReviewRow)
            .where(
                HandsOnReviewRow.owner_id == owner_id,
                HandsOnReviewRow.work_id == work_id,
            )
            .order_by(HandsOnReviewRow.created_at)
        ).all()
        return tuple(_review(row) for row in rows)

    def add_review(self, review):
        values = review.__dict__.copy()
        values["review_mode"] = review.review_mode.value
        self._session.add(HandsOnReviewRow(**values))
        self._session.flush()
        return review

    def list_questions(self, owner_id, work_id):
        rows = self._session.scalars(
            select(HandsOnCrossQuestionRow)
            .where(
                HandsOnCrossQuestionRow.owner_id == owner_id,
                HandsOnCrossQuestionRow.work_id == work_id,
            )
            .order_by(HandsOnCrossQuestionRow.created_at)
        ).all()
        return tuple(_question(row) for row in rows)

    def add_question(self, question):
        self._session.add(HandsOnCrossQuestionRow(**question.__dict__))
        self._session.flush()
        return question


def _work(r):
    return HandsOnWork(
        r.id,
        r.owner_id,
        r.goal_id,
        r.topic_stable_id,
        r.scenario_title,
        r.scenario_prompt,
        r.role,
        r.level,
        tuple(json.loads(r.constraints_json)),
        r.scenario_status,
        r.scenario_source,
        r.created_at,
    )


def _artifact(r):
    return HandsOnArtifact(
        r.id,
        r.owner_id,
        r.goal_id,
        r.work_id,
        r.revision_number,
        r.content,
        r.content_hash,
        r.response_to_question_id,
        r.cross_question_response,
        r.evidence_id,
        r.created_at,
    )


def _review(r):
    return HandsOnReview(
        r.id,
        r.owner_id,
        r.goal_id,
        r.work_id,
        r.artifact_id,
        r.assessment_id,
        ReviewMode(r.review_mode),
        r.required_limitation_label,
        r.created_at,
    )


def _question(r):
    return HandsOnCrossQuestion(
        r.id,
        r.owner_id,
        r.goal_id,
        r.work_id,
        r.review_id,
        r.artifact_id,
        r.question,
        r.target_gap,
        r.created_at,
    )

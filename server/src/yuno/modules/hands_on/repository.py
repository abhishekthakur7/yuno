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
    HandsOnArtifactBodyRow,
    HandsOnArtifactRow,
    HandsOnCrossQuestionBodyRow,
    HandsOnCrossQuestionRow,
    HandsOnReviewBodyRow,
    HandsOnReviewRow,
    HandsOnWorkBodyRow,
    HandsOnWorkRow,
)
from yuno.shared.domain.hashing import hash_payload


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
        return (
            _work(row, self._session.get(HandsOnWorkBodyRow, row.id)) if row else None
        )

    def add_work(self, work):
        values = work.__dict__.copy()
        body = {
            key: values.pop(key)
            for key in (
                "scenario_title",
                "scenario_prompt",
                "role",
                "level",
                "scenario_source",
            )
        }
        body["constraints_json"] = json.dumps(values.pop("constraints"))
        values["body_hash"] = hash_payload(body)
        self._session.add(HandsOnWorkRow(**values))
        self._session.flush()
        self._session.add(
            HandsOnWorkBodyRow(
                work_id=work.id,
                owner_id=work.owner_id,
                goal_id=work.goal_id,
                **body,
            )
        )
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
        return tuple(self._artifact(row) for row in rows)

    def get_artifact(self, owner_id, artifact_id):
        row = self._session.scalar(
            select(HandsOnArtifactRow).where(
                HandsOnArtifactRow.owner_id == owner_id,
                HandsOnArtifactRow.id == artifact_id,
            )
        )
        return self._artifact(row) if row else None

    def get_artifact_by_evidence(self, owner_id, evidence_id):
        row = self._session.scalar(
            select(HandsOnArtifactRow).where(
                HandsOnArtifactRow.owner_id == owner_id,
                HandsOnArtifactRow.evidence_id == evidence_id,
            )
        )
        return self._artifact(row) if row else None

    def add_artifact(self, artifact):
        values = artifact.__dict__.copy()
        values.pop("content")
        response = values.pop("cross_question_response")
        values["body_hash"] = hash_payload(response)
        self._session.add(HandsOnArtifactRow(**values))
        self._session.flush()
        self._session.add(
            HandsOnArtifactBodyRow(
                artifact_id=artifact.id,
                owner_id=artifact.owner_id,
                goal_id=artifact.goal_id,
                cross_question_response=response,
            )
        )
        self._session.flush()
        return artifact

    def get_question(self, owner_id, question_id):
        row = self._session.scalar(
            select(HandsOnCrossQuestionRow).where(
                HandsOnCrossQuestionRow.owner_id == owner_id,
                HandsOnCrossQuestionRow.id == question_id,
            )
        )
        return (
            _question(row, self._session.get(HandsOnCrossQuestionBodyRow, row.id))
            if row
            else None
        )

    def list_reviews(self, owner_id, work_id):
        rows = self._session.scalars(
            select(HandsOnReviewRow)
            .where(
                HandsOnReviewRow.owner_id == owner_id,
                HandsOnReviewRow.work_id == work_id,
            )
            .order_by(HandsOnReviewRow.created_at)
        ).all()
        return tuple(
            review
            for row in rows
            if (review := _review(row, self._session.get(HandsOnReviewBodyRow, row.id)))
            is not None
        )

    def add_review(self, review):
        values = review.__dict__.copy()
        values["review_mode"] = review.review_mode.value
        limitation = values.pop("required_limitation_label")
        values["body_hash"] = hash_payload(limitation)
        self._session.add(HandsOnReviewRow(**values))
        self._session.flush()
        self._session.add(
            HandsOnReviewBodyRow(
                review_id=review.id,
                owner_id=review.owner_id,
                goal_id=review.goal_id,
                required_limitation_label=limitation,
            )
        )
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
        return tuple(
            question
            for row in rows
            if (
                question := _question(
                    row, self._session.get(HandsOnCrossQuestionBodyRow, row.id)
                )
            )
            is not None
        )

    def add_question(self, question):
        values = question.__dict__.copy()
        body = {
            "question": values.pop("question"),
            "target_gap": values.pop("target_gap"),
        }
        values["body_hash"] = hash_payload(body)
        self._session.add(HandsOnCrossQuestionRow(**values))
        self._session.flush()
        self._session.add(
            HandsOnCrossQuestionBodyRow(
                question_id=question.id,
                owner_id=question.owner_id,
                goal_id=question.goal_id,
                **body,
            )
        )
        self._session.flush()
        return question

    def _artifact(self, row):
        body = self._session.get(HandsOnArtifactBodyRow, row.id)
        return HandsOnArtifact(
            row.id,
            row.owner_id,
            row.goal_id,
            row.work_id,
            row.revision_number,
            "",
            row.content_hash,
            row.response_to_question_id,
            body.cross_question_response if body else None,
            row.evidence_id,
            row.created_at,
        )


def _work(r, body):
    if body is None:
        return None
    return HandsOnWork(
        r.id,
        r.owner_id,
        r.goal_id,
        r.topic_stable_id,
        body.scenario_title,
        body.scenario_prompt,
        body.role,
        body.level,
        tuple(json.loads(body.constraints_json)),
        r.scenario_status,
        body.scenario_source,
        r.created_at,
    )


def _review(r, body):
    if body is None:
        return None
    return HandsOnReview(
        r.id,
        r.owner_id,
        r.goal_id,
        r.work_id,
        r.artifact_id,
        r.assessment_id,
        ReviewMode(r.review_mode),
        body.required_limitation_label,
        r.created_at,
    )


def _question(r, body):
    if body is None:
        return None
    return HandsOnCrossQuestion(
        r.id,
        r.owner_id,
        r.goal_id,
        r.work_id,
        r.review_id,
        r.artifact_id,
        body.question,
        body.target_gap,
        r.created_at,
    )

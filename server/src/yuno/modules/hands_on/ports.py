from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.hands_on.domain import (
    HandsOnArtifact,
    HandsOnCrossQuestion,
    HandsOnReview,
    HandsOnWork,
)
from yuno.shared.application.unit_of_work import UnitOfWork


class HandsOnRepository(Protocol):
    def get_work(
        self, owner_id: str, goal_id: str, topic_id: str
    ) -> HandsOnWork | None: ...
    def add_work(self, work: HandsOnWork) -> HandsOnWork: ...
    def list_artifacts(
        self, owner_id: str, work_id: str
    ) -> Sequence[HandsOnArtifact]: ...
    def get_artifact(
        self, owner_id: str, artifact_id: str
    ) -> HandsOnArtifact | None: ...
    def get_artifact_by_evidence(
        self, owner_id: str, evidence_id: str
    ) -> HandsOnArtifact | None: ...
    def add_artifact(self, artifact: HandsOnArtifact) -> HandsOnArtifact: ...
    def get_question(
        self, owner_id: str, question_id: str
    ) -> HandsOnCrossQuestion | None: ...
    def list_reviews(self, owner_id: str, work_id: str) -> Sequence[HandsOnReview]: ...
    def add_review(self, review: HandsOnReview) -> HandsOnReview: ...
    def list_questions(
        self, owner_id: str, work_id: str
    ) -> Sequence[HandsOnCrossQuestion]: ...
    def add_question(self, question: HandsOnCrossQuestion) -> HandsOnCrossQuestion: ...


class HandsOnUnitOfWork(UnitOfWork, Protocol):
    hands_on: HandsOnRepository
    evidence: object
    profiles_goals: object
    canonical: object
    audit: object

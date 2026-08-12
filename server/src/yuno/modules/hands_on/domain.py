from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReviewMode(StrEnum):
    STATIC = "static"


@dataclass(frozen=True)
class HandsOnWork:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    scenario_title: str
    scenario_prompt: str
    role: str
    level: str
    constraints: tuple[str, ...]
    scenario_status: str
    scenario_source: str
    created_at: str


@dataclass(frozen=True)
class HandsOnArtifact:
    id: str
    owner_id: str
    goal_id: str
    work_id: str
    revision_number: int
    content: str
    content_hash: str
    response_to_question_id: str | None
    cross_question_response: str | None
    evidence_id: str
    created_at: str


@dataclass(frozen=True)
class HandsOnReview:
    id: str
    owner_id: str
    goal_id: str
    work_id: str
    artifact_id: str
    assessment_id: str
    review_mode: ReviewMode
    required_limitation_label: str
    created_at: str


@dataclass(frozen=True)
class HandsOnCrossQuestion:
    id: str
    owner_id: str
    goal_id: str
    work_id: str
    review_id: str
    artifact_id: str
    question: str
    target_gap: str
    created_at: str

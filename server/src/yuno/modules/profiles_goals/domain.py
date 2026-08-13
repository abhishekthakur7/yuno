"""Framework-free profile and goal domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from yuno.shared.domain.errors import DomainValidationError


class GoalPath(StrEnum):
    LEARN = "learn"
    INTERVIEW_PREP = "interview_prep"


class TargetLevel(StrEnum):
    MID_LEVEL = "Mid-level"
    SENIOR = "Senior"
    STAFF = "Staff"


class TargetCapability(StrEnum):
    KNOW = "know"
    UNDERSTAND = "understand"
    CHOOSE = "choose"
    IMPLEMENT = "implement"
    DIAGNOSE = "diagnose"
    DEFEND = "defend"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    TOMBSTONED = "tombstoned"


class ResumeDestination(StrEnum):
    LEARN_ROADMAP = "/app/learn-roadmap"
    TOPIC_STUDIO = "/app/topic-studio"
    INTERVIEW_HUB = "/app/interview-hub"
    PRACTICE = "/app/practice"
    MOCK = "/app/mock"


@dataclass(frozen=True)
class LearnerProfile:
    owner_id: str
    experience: str | None
    strengths: str | None
    weaknesses: str | None
    current_goal_id: str | None
    profile_revision: int
    updated_at: str


@dataclass(frozen=True)
class GoalWorkspace:
    id: str
    owner_id: str
    name: str
    path: GoalPath
    subject: str | None
    role: str | None
    target_level: TargetLevel
    target_capability: TargetCapability
    graph_version_id: str
    status: GoalStatus
    resume_position: str | None
    last_accessed_at: str | None
    row_version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class GoalLifecycle:
    id: str
    owner_id: str
    status: GoalStatus
    row_version: int


@dataclass(frozen=True)
class GoalNavigationEvent:
    id: str
    owner_id: str
    goal_id: str
    position: str | None
    destination: ResumeDestination
    occurred_at: str


@dataclass(frozen=True)
class RecommendationDismissal:
    id: str
    owner_id: str
    goal_id: str
    recommendation_key: str
    dismissed_at: str


@dataclass(frozen=True)
class IdempotencyRecord:
    id: str
    owner_id: str
    operation: str
    idempotency_key: str
    request_hash: str
    goal_id: str
    response_json: str
    created_at: str


def validate_resume_destination(path: GoalPath, destination: ResumeDestination) -> None:
    allowed = {
        GoalPath.LEARN: {
            ResumeDestination.LEARN_ROADMAP,
            ResumeDestination.TOPIC_STUDIO,
            ResumeDestination.PRACTICE,
        },
        GoalPath.INTERVIEW_PREP: {
            ResumeDestination.INTERVIEW_HUB,
            ResumeDestination.PRACTICE,
            ResumeDestination.MOCK,
        },
    }
    if destination not in allowed[path]:
        raise DomainValidationError(
            f"Resume destination '{destination.value}' is not valid for a {path.value} goal."
        )


def validate_goal_fields(
    *,
    name: str,
    path: GoalPath,
    subject: str | None,
    role: str | None,
) -> None:
    if not name.strip():
        raise DomainValidationError("Goal name must not be blank.")
    if path is GoalPath.LEARN and not (subject and subject.strip()):
        raise DomainValidationError("A Learn goal requires a subject.")
    if path is GoalPath.LEARN and role is not None:
        raise DomainValidationError("A Learn goal must not specify a role.")
    if path is GoalPath.INTERVIEW_PREP and not (role and role.strip()):
        raise DomainValidationError("An Interview Prep goal requires a role.")
    if path is GoalPath.INTERVIEW_PREP and subject is not None:
        raise DomainValidationError(
            "An Interview Prep goal must not specify a subject."
        )

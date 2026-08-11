"""Pydantic response contracts (spec §5.1).

FastAPI serializes every API response through one of these models. Domain
and application code never imports pydantic (spec §3.2's dependency
direction) and knows nothing about these shapes — translating domain
dataclasses (`YunoError`, `JobRef`) into them happens only here and in
`yuno.api.errors`.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from yuno.modules.profiles_goals.domain import (
    GoalPath,
    GoalStatus,
    ResumeDestination,
    TargetCapability,
    TargetLevel,
)
from yuno.shared.application.jobs import JobRef, JobStatus


class FieldError(BaseModel):
    """One entry of `ErrorResponse.field_errors`. The domain layer leaves
    `YunoError.field_errors` generic (`Sequence[Mapping[str, Any]]`); a
    caller must supply mappings with exactly these two keys.
    """

    field: str
    message: str


class ErrorResponse(BaseModel):
    """The spec §5.1 error envelope: every `YunoError`, request validation
    failure, and unhandled exception renders through this shape (see
    `yuno.api.errors.register_exception_handlers`).
    """

    code: str
    message: str
    request_id: str
    correlation_id: str
    retryable: bool
    field_errors: list[FieldError] | None = None
    current_state: str | None = None
    job_id: str | None = None
    recovery_action: str | None = None


class JobRefResponse(BaseModel):
    """Mirrors `application.jobs.JobRef` — the `202` enqueue response body
    every async endpoint returns via `accepted_job`.
    """

    job_id: str
    kind: str
    status: JobStatus
    enqueued_at: str
    deduplicated: bool = False


class HealthResponse(BaseModel):
    """`GET /api/v1/health` response body."""

    status: str
    schema_revision: str


class LearnerProfileResponse(BaseModel):
    experience: str | None
    strengths: str | None
    weaknesses: str | None
    current_goal_id: str | None
    profile_revision: int
    updated_at: str


class LearnerProfilePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experience: str | None = None
    strengths: str | None = None
    weaknesses: str | None = None


class GoalCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    path: GoalPath
    subject: str | None = None
    role: str | None = None
    target_level: TargetLevel
    target_capability: TargetCapability
    graph_version_id: str


class GoalPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    subject: str | None = None
    role: str | None = None
    target_level: TargetLevel | None = None
    target_capability: TargetCapability | None = None
    resume_position: str | None = None
    resume_destination: ResumeDestination | None = None
    dismiss_recommendation_key: str | None = None
    set_current: bool | None = None


class GoalResponse(BaseModel):
    id: str
    name: str
    path: GoalPath
    subject: str | None
    role: str | None
    target_level: TargetLevel
    target_capability: TargetCapability
    graph_version_id: str
    status: GoalStatus
    resume_position: str | None
    resume_destination: ResumeDestination | None
    last_accessed_at: str | None
    dismissed_recommendation_keys: list[str]
    row_version: int
    created_at: str
    updated_at: str


class CanonicalVersionSummaryResponse(BaseModel):
    """One entry of `GET /api/v1/canonical/versions` (spec §5.2). Mirrors
    `modules.canonical.domain.CanonicalGraphVersion`, minus the internal
    `creator_owner_id` -- see `yuno.api.routes.canonical` for why callers
    never see who ran the offline publisher.
    """

    id: str
    version_label: str
    manifest_version: str
    created_at: str
    published_at: str | None
    supersedes_version_id: str | None


class CanonicalTopicResponse(BaseModel):
    """One `Topic` row nested in `CanonicalVersionDetailResponse.topics`."""

    stable_id: str
    title: str
    subject: str
    scope_tags: list[str]
    level_tag: str
    target_capability: str
    recommended_layer: str
    checkpoint_start: int
    checkpoint_end: int


class CanonicalTopicRelationResponse(BaseModel):
    """One `TopicRelation` row nested in
    `CanonicalVersionDetailResponse.relations`."""

    id: str
    from_stable_id: str
    to_stable_id: str
    relation_type: str
    rationale: str | None


class CanonicalVersionDetailResponse(CanonicalVersionSummaryResponse):
    """`GET /api/v1/canonical/versions/{id}` response body: the version
    plus its published topics and relations (spec §5.2). Nests, rather
    than requiring separate topic/relation calls, since a caller reading
    one canonical graph version wants its whole shape in one round trip
    and both are approval-gated identically (`ports.py`'s
    `get_published_topics`/`get_published_relations`).
    """

    topics: list[CanonicalTopicResponse]
    relations: list[CanonicalTopicRelationResponse]


def accepted_job(job_ref: JobRef) -> JSONResponse:
    """Build the `202 Accepted` response every async endpoint returns on
    enqueue, so the shape stays identical everywhere.
    """
    body = JobRefResponse(
        job_id=job_ref.job_id,
        kind=job_ref.kind,
        status=job_ref.status,
        enqueued_at=job_ref.enqueued_at,
        deduplicated=job_ref.deduplicated,
    )
    return JSONResponse(status_code=202, content=body.model_dump(mode="json"))

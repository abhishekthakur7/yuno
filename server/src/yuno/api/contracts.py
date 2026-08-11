"""Pydantic response contracts (spec §5.1).

FastAPI serializes every API response through one of these models. Domain
and application code never imports pydantic (spec §3.2's dependency
direction) and knows nothing about these shapes — translating domain
dataclasses (`YunoError`, `JobRef`) into them happens only here and in
`yuno.api.errors`.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from yuno.modules.diagnostics.domain import (
    DiagnosticAction,
    DiagnosticConfidence,
    DiagnosticPath,
    DiagnosticState,
    DiagnosticTargetCapability,
    DiagnosticTargetLevel,
    UntrustedSeedKind,
)
from yuno.modules.profiles_goals.domain import (
    GoalPath,
    GoalStatus,
    ResumeDestination,
    TargetCapability,
    TargetLevel,
)
from yuno.modules.roadmap.domain import CorrectionType, LearningClassification
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


class DiagnosticCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: DiagnosticPath
    subject: str | None = None
    role: str | None = None
    target_level: DiagnosticTargetLevel
    target_capability: DiagnosticTargetCapability
    graph_version_id: str
    setup_inputs: dict[str, object] = Field(default_factory=dict)


class DiagnosticPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: DiagnosticAction | None = None
    untrusted_seed_text: str | None = None


class DiagnosticAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_ref: str
    answer: str
    confidence: DiagnosticConfidence


class DiagnosticQuestionResponse(BaseModel):
    ref: str
    prompt: str
    sequence: int
    adaptive_context_version: str


class DiagnosticAnswerResponse(BaseModel):
    id: str
    sequence: int
    question_ref: str
    answer: str
    confidence: DiagnosticConfidence
    adaptive_context_version: str
    answered_at: str


class DiagnosticResponse(BaseModel):
    id: str
    captured_graph_version_id: str
    question_set_version: str
    setup_inputs: dict[str, object]
    state: DiagnosticState
    untrusted_seed_kind: UntrustedSeedKind | None
    untrusted_seed_text: str | None
    seed_skipped: bool
    diagnostic_skipped: bool
    answers: list[DiagnosticAnswerResponse]
    next_question: DiagnosticQuestionResponse | None
    started_at: str | None
    paused_at: str | None
    expires_at: str | None
    failure_code: str | None
    failure_reference: str | None
    confirmed_goal_id: str | None
    row_version: int
    created_at: str
    updated_at: str


class DiagnosticRoadmapPreviewResponse(BaseModel):
    session_id: str
    captured_graph_version_id: str
    state: DiagnosticState
    answer_count: int
    diagnostic_skipped: bool
    projection_version: str
    topic_recommendations: list[dict[str, object]]
    saved_edits: list[dict[str, object]]


class RoadmapTopicResponse(BaseModel):
    stable_id: str
    title: str
    subject: str
    scope_tags: list[str]
    level_tag: str
    target_capability: str
    recommended_depth: str
    depth_override: str | None
    is_skipped: bool
    classification: LearningClassification
    explanation: str
    has_transferred_evidence: bool
    pending_proposals: list[dict[str, object]]
    conflicts: list[dict[str, object]]


class RoadmapResponse(BaseModel):
    goal_id: str
    graph_version_id: str
    projection_version: str
    state: str
    topics: list[RoadmapTopicResponse]


class LearningStateResponse(BaseModel):
    topic_stable_id: str
    classification: LearningClassification
    origin: str
    recommended_depth: str
    explanation: str
    corrected_classification: LearningClassification | None = None


class RoadmapMutationResponse(BaseModel):
    projection: RoadmapResponse
    checkpoint_saved: bool = True


class LearnerCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_stable_id: str
    classification: LearningClassification
    correction_type: CorrectionType = CorrectionType.CORRECTION
    reason: str | None = None


class OrderConstraintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    before_topic_id: str
    after_topic_id: str
    reason: str | None = None


class SkipDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_stable_id: str
    skipped: bool
    reason: str | None = None


class DepthOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_stable_id: str
    depth: str | None
    reason: str | None = None


class DiagnosticPreviewEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_stable_id: str | None = None
    entry_type: str
    value: dict[str, object]
    reason: str | None = None


class DiagnosticRoadmapPreviewUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edits: list[DiagnosticPreviewEditRequest] = Field(default_factory=list)


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

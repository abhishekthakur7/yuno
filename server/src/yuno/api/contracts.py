"""Pydantic API contracts."""

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
from yuno.modules.evidence_evaluation.domain import (
    AssessmentState,
    DimensionOutcome,
    DisputeStatus,
    ProgressClassification,
)
from yuno.modules.imports.domain import (
    ImportStatus,
    ImportType,
    MappingDecision,
    MappingState,
    TrustState,
)
from yuno.modules.learning_content.domain import Capability, LayerState, TopicLayer
from yuno.modules.profiles_goals.domain import (
    GoalPath,
    GoalStatus,
    ResumeDestination,
    TargetCapability,
    TargetLevel,
)
from yuno.modules.roadmap.domain import (
    CorrectionType,
    LearningClassification,
    OverlayDecisionType,
    OverlayProposalState,
    OverlayProposalType,
)
from yuno.shared.application.jobs import JobRef, JobStatus


class FieldError(BaseModel):
    """One field-level error in the API error envelope."""

    field: str
    message: str


class ErrorResponse(BaseModel):
    """The API error envelope."""

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
    """The `202` response for an asynchronous operation."""

    job_id: str
    kind: str
    status: JobStatus
    enqueued_at: str
    deduplicated: bool = False


class HealthResponse(BaseModel):
    status: str
    schema_revision: str


class ProgressDimensionResponse(BaseModel):
    classification: ProgressClassification
    definition: str
    supporting_evidence_refs: list[str]
    uncertainty: str


class LearningStateExplanationResponse(BaseModel):
    topic_stable_id: str
    classification: ProgressClassification
    definition: str
    supporting_evidence_refs: list[str]
    uncertainty: str
    correction_ref: str | None


class GoalProgressResponse(BaseModel):
    coverage: ProgressDimensionResponse
    proficiency: ProgressDimensionResponse
    retention: ProgressDimensionResponse
    readiness: ProgressDimensionResponse
    rule_version: str
    effective_now: str
    input_hash: str
    authoritative: bool = False


class LearningStateExplanationsResponse(BaseModel):
    learning_states: list[LearningStateExplanationResponse]
    rule_version: str
    effective_now: str
    input_hash: str
    authoritative: bool = False


class ImportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal_id: str | None = None
    import_type: ImportType
    original_content: str


class ImportRecordResponse(BaseModel):
    id: str
    goal_id: str | None
    import_type: ImportType
    original_content: str
    original_hash: str
    parser_version: str
    status: ImportStatus
    failure_code: str | None
    failure_reference: str | None
    row_version: int
    created_at: str
    updated_at: str


class ImportStatementPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    corrected_text: str


class ImportStatementMapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal_id: str
    topic_id: str


class ImportStatementMappingResponse(BaseModel):
    goal_id: str
    topic_id: str
    graph_version_id: str
    decision: MappingDecision
    accepted_at: str
    revoked_at: str | None


class TopicImportHashResponse(BaseModel):
    goal_id: str
    graph_version_id: str
    topic_id: str
    imports_hash: str
    updated_at: str


class ImportStatementResponse(BaseModel):
    id: str
    import_id: str
    sequence: int
    parser_version: str
    original_text: str
    original_hash: str
    normalized_text: str
    normalized_hash: str
    confidence: float
    duplicate_of_statement_id: str | None
    trust_state: TrustState
    mapping_state: MappingState
    corrected_text: str | None
    row_version: int
    created_at: str
    updated_at: str
    mapping: ImportStatementMappingResponse | None = None


class ImportStatementMapResponse(BaseModel):
    statement: ImportStatementResponse
    mapping: ImportStatementMappingResponse
    topic_imports_hash: TopicImportHashResponse


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


class GoalDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: str


class GoalDeleteImpactResponse(BaseModel):
    snapshot_id: str
    goal_id: str
    evidence_ids: list[str]
    learning_state_ids: list[str]


class EvidenceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_stable_id: str
    evidence_type: str
    capability: str
    summary: str
    origin: str
    content: str
    content_version: str


class EvidenceResponse(BaseModel):
    id: str
    goal_id: str
    topic_stable_id: str
    evidence_type: str
    capability: str
    payload_hash: str
    summary: str
    origin: str
    created_at: str


class EvidenceDetailResponse(EvidenceResponse):
    content: str | None
    content_version: str | None
    tombstoned: bool


class AssessmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rubric_id: str
    rubric_version: str
    task_ref: str
    assumptions: list[str] = Field(default_factory=list)
    requested_capability: str
    source_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    role: str | None = None
    level: str | None = None
    evaluation_method: str
    run_id: str | None = None


class AssessmentDimensionResponse(BaseModel):
    dimension_id: str
    outcome: DimensionOutcome
    rationale: str
    evidence_refs: list[str]


class AssessmentResponse(BaseModel):
    id: str
    goal_id: str
    evidence_id: str
    run_id: str | None
    rubric_id: str
    rubric_version: str
    state: AssessmentState
    task_ref: str
    requested_capability: str
    role: str | None
    level: str | None
    evaluation_method: str
    assumptions: list[str]
    source_refs: list[str]
    provenance_refs: list[str]
    facts: list[str]
    trade_offs: list[str]
    citations: list[str]
    ambiguities: list[str]
    feedback: str
    cross_question_candidate: str | None
    revision_invitation: str | None
    warnings: list[str]
    limitation_labels: list[str]
    predecessor_assessment_id: str | None
    derivation_excluded: bool
    created_at: str
    dimensions: list[AssessmentDimensionResponse]


class AssessmentDisputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str


class AssessmentDisputeResponse(BaseModel):
    id: str
    goal_id: str
    assessment_id: str
    reason: str
    status: DisputeStatus
    requested_at: str


class AssessmentReevaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dispute_id: str


class TopicCheckpointResponse(BaseModel):
    scenario: str
    constraints: list[str]
    target_capability: Capability
    expected_artifact: str
    estimated_minutes: int = Field(ge=30, le=60)
    rubric: list[str]
    assumptions: list[str]
    evidence_criterion: str
    limitation: str


class TopicLayerResponse(BaseModel):
    layer: TopicLayer
    state: LayerState
    revision_id: str | None
    markdown: str | None
    markdown_hash: str | None
    checkpoint: TopicCheckpointResponse | None


class TopicLayersResponse(BaseModel):
    goal_id: str
    graph_version_id: str
    topic_id: str
    conversation_scope: str
    layers: list[TopicLayerResponse]


class TopicDetailResponse(BaseModel):
    graph_version_id: str
    stable_id: str
    title: str
    subject: str
    scope_tags: list[str]
    level_tag: str
    target_capability: Capability
    recommended_layer: str


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


class OverlayProposalCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generated_against_graph_version_id: str
    topic_stable_id: str | None = None
    proposal_type: OverlayProposalType
    payload: dict[str, object]


class OverlayProposalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: OverlayDecisionType
    reason: str | None = None


class OverlayProposalDecisionResponse(BaseModel):
    id: str
    decision: OverlayDecisionType
    reason: str | None
    decided_at: str


class OverlayProposalResponse(BaseModel):
    id: str
    goal_id: str
    generated_against_graph_version_id: str
    topic_stable_id: str | None
    proposal_type: OverlayProposalType
    payload: dict[str, object]
    content_hash: str
    state: OverlayProposalState
    state_reason: str | None
    created_at: str
    decided_at: str | None
    deduplicated: bool = False
    decisions: list[OverlayProposalDecisionResponse] = Field(default_factory=list)


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

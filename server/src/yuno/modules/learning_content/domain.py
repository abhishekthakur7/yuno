"""Topic-layer types and validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from yuno.shared.domain.errors import DomainValidationError
from yuno.shared.domain.hashing import hash_payload

EMPTY_IMPORTS_HASH = hash_payload([])
PROMPT_TEMPLATE_VERSION = "provider-prompt-v1"
GENERATION_SCHEMA_VERSION = "generate-result-v1"


class TopicLayer(StrEnum):
    ESSENTIAL = "Essential"
    IMPLEMENTATION = "Implementation"
    INTERNALS = "Internals"
    PRODUCTION = "Production"
    ALTERNATIVES = "Alternatives"
    FAILURES = "Failures"
    INTERVIEW = "Interview"
    SOURCES = "Sources"


class Capability(StrEnum):
    KNOW = "know"
    UNDERSTAND = "understand"
    CHOOSE = "choose"
    IMPLEMENT = "implement"
    DIAGNOSE = "diagnose"
    DEFEND = "defend"


class LayerState(StrEnum):
    READY = "ready"
    ABSENT = "absent"
    GENERATING = "generating"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class ArtifactState(StrEnum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class GenerationAttemptStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class StaleReason(StrEnum):
    PERSONALIZATION_SNAPSHOT_MISMATCH = "personalization-snapshot-mismatch"
    CACHE_KEY_CHANGED = "cache-key-changed"


@dataclass(frozen=True)
class D3CacheKey:
    canonical_graph_version: str
    topic_id: str
    goal_id: str
    layer: TopicLayer
    topic_mapped_approved_imports_hash: str
    prompt_template_version: str


def d3_cache_key_hash(key: D3CacheKey) -> str:
    values = {
        "canonical_graph_version": key.canonical_graph_version,
        "topic_id": key.topic_id,
        "goal_id": key.goal_id,
        "layer": key.layer.value,
        "topic_mapped_approved_imports_hash": key.topic_mapped_approved_imports_hash,
        "prompt_template_version": key.prompt_template_version,
    }
    if any(not str(value).strip() for value in values.values()):
        raise DomainValidationError("Every D3 cache-key component must be non-blank.")
    return hash_payload(values)


def personalization_is_stale(
    baked_snapshot_hash: str, current_snapshot_hash: str
) -> bool:
    """Pure D3 comparison; mismatch never authorizes replacing the cached body."""
    return baked_snapshot_hash != current_snapshot_hash


def evaluate_artifact_staleness(
    baked_cache_key_hash: str,
    current_cache_key_hash: str,
    baked_snapshot_hash: str,
    current_snapshot_hash: str,
) -> tuple[StaleReason, ...]:
    reasons = []
    if baked_cache_key_hash != current_cache_key_hash:
        reasons.append(StaleReason.CACHE_KEY_CHANGED)
    if baked_snapshot_hash != current_snapshot_hash:
        reasons.append(StaleReason.PERSONALIZATION_SNAPSHOT_MISMATCH)
    return tuple(reasons)


@dataclass(frozen=True)
class GeneratedArtifact:
    id: str
    owner_id: str
    goal_id: str
    graph_version_id: str
    topic_stable_id: str
    layer: TopicLayer
    artifact_type: str
    imports_hash: str
    prompt_template_version: str
    cache_key_hash: str
    state: ArtifactState
    body: str | None
    body_hash: str | None
    current_snapshot_id: str | None
    producing_job_id: str | None
    last_attempt_id: str | None
    last_job_id: str | None
    last_attempt_status: GenerationAttemptStatus | None
    failure_reference: str | None
    retryable: bool
    row_version: int
    created_at: str
    updated_at: str
    generated_at: str | None


@dataclass(frozen=True)
class GenerationAttempt:
    id: str
    owner_id: str
    goal_id: str
    artifact_id: str
    cache_key_hash: str
    job_id: str
    kind: str
    status: GenerationAttemptStatus
    request_hash: str
    result_hash: str | None
    failure_classification: str | None
    failure_reference: str | None
    retryable: bool
    created_at: str
    started_at: str | None
    completed_at: str | None


@dataclass(frozen=True)
class GenerateRequest:
    owner_id: str
    goal_id: str
    topic_id: str
    layer: TopicLayer
    graph_version: str
    imports_hash: str
    prompt_template_version: str
    profile_hash: str
    evidence_state_hash: str


@dataclass(frozen=True)
class GenerateResult:
    body: str
    provider: str
    model: str
    contract_version: str
    schema_version: str
    generated_at: str
    provenance_refs: tuple[tuple[str, str], ...] = ()
    claims: tuple[GeneratedClaim, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneratedCitation:
    source_id: str
    source_snapshot_id: str | None
    locator: str
    support_kind: str
    note: str | None = None


@dataclass(frozen=True)
class GeneratedClaim:
    claim_text: str
    claim_type: str
    sensitive: bool = False
    citations: tuple[GeneratedCitation, ...] = ()


@dataclass(frozen=True)
class GenerationIdempotencyRecord:
    id: str
    owner_id: str
    operation: str
    idempotency_key: str
    request_hash: str
    attempt_id: str
    job_id: str
    response_json: str
    created_at: str


class ConversationRole(StrEnum):
    LEARNER = "learner"
    TUTOR = "tutor"


@dataclass(frozen=True)
class TopicConversationTurn:
    id: str
    owner_id: str
    goal_id: str
    graph_version_id: str
    topic_stable_id: str
    role: ConversationRole
    body: str
    response_to_id: str | None
    job_id: str | None
    idempotency_key: str | None
    request_hash: str | None
    created_at: str


@dataclass(frozen=True)
class TutorRequest:
    owner_id: str
    goal_id: str
    graph_version_id: str
    topic_id: str
    learner_turn_id: str
    message: str
    conversation: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TutorResult:
    body: str
    provenance_references: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class GenerationSnapshot:
    id: str
    owner_id: str
    goal_id: str
    artifact_id: str
    attempt_id: str
    evidence_state_hash: str
    profile_hash: str
    provider: str
    model: str
    generated_at: str
    schema_version: str
    contract_version: str
    prompt_template_version: str
    snapshot_hash: str


@dataclass(frozen=True)
class GenerationProvenanceRef:
    id: str
    owner_id: str
    goal_id: str
    artifact_id: str
    snapshot_id: str
    ref_kind: str
    reference_id: str


@dataclass(frozen=True)
class GenerationClaimRecord:
    id: str
    owner_id: str
    goal_id: str | None
    content_revision_id: str | None
    generated_artifact_id: str | None
    snapshot_id: str | None
    claim_text: str
    claim_type: str
    sensitive: bool
    status: str


@dataclass(frozen=True)
class GenerationCitationRecord:
    id: str
    owner_id: str
    goal_id: str
    claim_id: str
    source_id: str
    source_snapshot_id: str | None
    locator: str
    support_kind: str
    note: str | None


@dataclass(frozen=True)
class Checkpoint:
    scenario: str
    constraints: tuple[str, ...]
    target_capability: Capability
    expected_artifact: str
    estimated_minutes: int
    rubric: tuple[str, ...]
    assumptions: tuple[str, ...]
    evidence_criterion: str
    limitation: str


@dataclass(frozen=True)
class LayerDocument:
    layer: TopicLayer
    state: LayerState
    revision_id: str | None
    markdown: str | None
    markdown_hash: str | None
    checkpoint: Checkpoint | None
    artifact_id: str | None = None
    content_origin: str | None = None
    generation: dict[str, object] | None = None
    stale_reason: StaleReason | None = None


@dataclass(frozen=True)
class MentalModelLayer:
    layer: TopicLayer
    claim_ids: tuple[str, ...]
    reverses_claim_ids: tuple[str, ...] = ()


def validate_checkpoint(checkpoint: Checkpoint) -> None:
    fields = {
        "scenario": checkpoint.scenario,
        "expected_artifact": checkpoint.expected_artifact,
        "evidence_criterion": checkpoint.evidence_criterion,
        "limitation": checkpoint.limitation,
    }
    for name, value in fields.items():
        if not value.strip():
            raise DomainValidationError(f"Checkpoint {name} must not be blank.")
    if not 30 <= checkpoint.estimated_minutes <= 60:
        raise DomainValidationError(
            "Checkpoint estimated_minutes must be between 30 and 60."
        )
    if not checkpoint.rubric:
        raise DomainValidationError("Checkpoint rubric must not be empty.")
    if not checkpoint.constraints:
        raise DomainValidationError("Checkpoint constraints must not be empty.")
    if not checkpoint.assumptions:
        raise DomainValidationError("Checkpoint assumptions must not be empty.")


def validate_layer_progression(layers: tuple[MentalModelLayer, ...]) -> None:
    seen_claims: set[str] = set()
    for layer in layers:
        reversed_claims = seen_claims.intersection(layer.reverses_claim_ids)
        if reversed_claims:
            names = ", ".join(sorted(reversed_claims))
            raise DomainValidationError(
                f"{layer.layer.value} reverses earlier mental-model claims: {names}."
            )
        seen_claims.update(layer.claim_ids)

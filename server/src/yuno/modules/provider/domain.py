"""Framework-free contracts and failure vocabulary for provider execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ProviderName(StrEnum):
    CODEX = "codex"
    CLAUDE = "claude"


class ProviderCapabilityState(StrEnum):
    CONFIGURED = "configured"
    UNAVAILABLE = "unavailable"


class ProviderResultState(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class ProviderFailureClassification(StrEnum):
    CONFIGURATION_OR_AUTHENTICATION = "provider-configuration-or-authentication"
    INACTIVITY_TIMEOUT = "inactivity-timeout"
    ABSOLUTE_TIMEOUT = "absolute-timeout"
    PROCESS_FAILED = "process-failed"
    CANCELLED = "cancelled"
    SCHEMA_INVALID = "schema-invalid"


@dataclass(frozen=True)
class ProviderTimers:
    first_output_seconds: float
    inactivity_seconds: float
    absolute_seconds: float

    def __post_init__(self) -> None:
        if (
            min(
                self.first_output_seconds,
                self.inactivity_seconds,
                self.absolute_seconds,
            )
            <= 0
        ):
            raise ValueError("Provider timers must all be positive.")


@dataclass(frozen=True)
class ProviderCapability:
    provider: ProviderName
    state: ProviderCapabilityState
    reason: str | None = None
    adapter_version: str | None = None
    contract_version: str | None = None


@dataclass(frozen=True)
class ProviderInput:
    owner_id: str
    goal_id: str | None
    job_id: str
    purpose: str
    context: Mapping[str, Any]
    context_ref_hash: str
    disclosure_id: str
    output_schema_version: str
    provider_request_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True)
class ProcessOutcome:
    pid: int
    pgid: int
    process_identity: str
    stdout: bytes
    stderr: bytes
    exit_code: int | None
    first_output_seen: bool
    timed_out: ProviderFailureClassification | None = None
    cancelled: bool = False
    truncated: bool = False


@dataclass(frozen=True)
class ProviderResult:
    state: ProviderResultState
    provider: ProviderName
    model: str | None
    contract_version: str
    schema_version: str
    payload: Mapping[str, Any] | None
    result_hash: str | None
    failure_classification: ProviderFailureClassification | None = None
    diagnostic_ref: str | None = None
    retryable: bool = False
    quarantine_id: str | None = None
    quarantine: QuarantineDetails | None = None
    timestamp: str | None = None
    provenance_references: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuarantineDetails:
    raw_output_ref: str
    raw_output_hash: str
    validation_errors: tuple[str, ...]


@dataclass(frozen=True)
class GenerateRequest:
    purpose: str
    owner_id: str
    goal_id: str
    topic_id: str
    layer: str
    graph_version: str
    context_references: tuple[str, ...]
    capability_target: str
    output_schema_version: str
    safety_mode: str
    provider_choice: ProviderName
    prompt_template_version: str
    disclosure_reference: str


@dataclass(frozen=True)
class EvaluationRequest:
    owner_id: str
    goal_id: str
    evidence_or_answer_references: tuple[str, ...]
    task_references: tuple[str, ...]
    rubric_id: str
    rubric_version: str
    assumptions: tuple[str, ...]
    requested_capability: str
    source_provenance_references: tuple[str, ...]
    role: str
    level: str
    method: str
    output_schema_version: str
    provider_choice: ProviderName
    disclosure_reference: str


@dataclass(frozen=True)
class EvaluationResult:
    dimensions: tuple[Mapping[str, Any], ...]
    facts: tuple[str, ...]
    trade_offs: tuple[str, ...]
    citations: tuple[Mapping[str, Any], ...]
    ambiguities: tuple[str, ...]
    feedback: str
    cross_question_candidate: str | None
    revision_invitation: str | None
    warnings: tuple[str, ...]
    limitation_labels: tuple[str, ...]


@dataclass(frozen=True)
class NetworkDisclosure:
    id: str
    owner_id: str
    category: str
    operation: str
    destination: str
    data_categories: tuple[str, ...]
    disclosure_version: str
    accepted_at: str
    revoked_at: str | None

    @property
    def active(self) -> bool:
        return self.revoked_at is None


@dataclass(frozen=True)
class SchemaQuarantine:
    id: str
    owner_id: str
    provider_request_id: str
    job_id: str
    raw_output_ref: str
    raw_output_hash: str
    expected_schema_version: str
    validation_errors: tuple[str, ...]
    created_at: str

"""Framework-free source registry contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    WITHDRAWN = "withdrawn"


class ClaimType(StrEnum):
    FACT = "fact"
    TRADE_OFF = "trade-off"
    ROUTINE = "routine"
    DISPUTED = "disputed"
    COMPARATIVE = "comparative"
    TIME_OR_VERSION_DEPENDENT = "time-or-version-dependent"


class ClaimStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"


@dataclass(frozen=True)
class Source:
    id: str
    owner_id: str
    origin: str
    source_type: str
    title: str
    publisher: str | None
    canonical_url: str | None
    license_status: str
    availability_status: SourceAvailability
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SourceSnapshot:
    id: str
    owner_id: str
    source_id: str
    retrieved_at: str
    content_ref: str
    content_hash: str
    status: str
    version_label: str | None


@dataclass(frozen=True)
class ArtifactProvenanceSnapshot:
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
class ArtifactProvenanceRef:
    id: str
    owner_id: str
    goal_id: str
    artifact_id: str
    snapshot_id: str
    ref_kind: str
    reference_id: str


@dataclass(frozen=True)
class Claim:
    id: str
    owner_id: str
    goal_id: str | None
    content_revision_id: str | None
    generated_artifact_id: str | None
    snapshot_id: str | None
    claim_text: str
    claim_type: ClaimType
    sensitive: bool
    status: ClaimStatus


@dataclass(frozen=True)
class Citation:
    id: str
    owner_id: str
    goal_id: str
    claim_id: str
    source_id: str
    source_snapshot_id: str | None
    locator: str
    support_kind: str
    note: str | None

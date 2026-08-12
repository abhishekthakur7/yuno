"""Evidence transfer and deletion types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TransferClassification(StrEnum):
    LIKELY_KNOWN = "likely-known"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    NEW = "new"


@dataclass(frozen=True)
class Evidence:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    evidence_type: str
    capability: str
    payload_hash: str
    summary: str
    origin: str
    created_at: str


@dataclass(frozen=True)
class EvidencePayload:
    evidence_id: str
    owner_id: str
    goal_id: str
    content: str
    content_version: str


@dataclass(frozen=True)
class TransferredEvidenceRef:
    id: str
    owner_id: str
    goal_id: str
    learning_state_id: str
    source_goal_id: str
    source_evidence_id: str
    classification: TransferClassification
    rationale: str
    created_at: str


@dataclass(frozen=True)
class EvidenceTombstone:
    evidence_id: str
    owner_id: str
    goal_id: str
    delete_operation_id: str
    reason: str
    tombstoned_at: str


@dataclass(frozen=True)
class TransferredLearningState:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    graph_version_id: str
    classification: TransferClassification
    origin: str
    recommended_depth: str
    explanation: str
    derivation_version: str
    input_hash: str
    derived_at: str


@dataclass(frozen=True)
class DeleteImpact:
    snapshot_id: str
    goal_id: str
    evidence_ids: tuple[str, ...]
    learning_state_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceDeleteSnapshot:
    id: str
    owner_id: str
    goal_id: str
    impact_json: str
    impact_hash: str
    created_at: str

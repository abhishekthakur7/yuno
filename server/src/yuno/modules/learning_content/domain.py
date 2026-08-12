"""Topic-layer types and validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from yuno.shared.domain.errors import DomainValidationError


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
    EMPTY = "empty"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


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

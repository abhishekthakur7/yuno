"""Source registry ports."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.provenance.domain import (
    ArtifactProvenanceRef,
    ArtifactProvenanceSnapshot,
    Citation,
    Claim,
    Source,
    SourceSnapshot,
)


class SourceRepository(Protocol):
    def add_source(self, source: Source) -> Source: ...
    def get_source(self, owner_id: str, source_id: str) -> Source | None: ...
    def list_sources(self, owner_id: str) -> Sequence[Source]: ...
    def get_source_snapshot(
        self, owner_id: str, snapshot_id: str
    ) -> SourceSnapshot | None: ...
    def add_generation_result(
        self,
        snapshot: ArtifactProvenanceSnapshot,
        refs: Sequence[ArtifactProvenanceRef],
        claims: Sequence[tuple[Claim, Sequence[Citation]]],
    ) -> None: ...
    def get_artifact_snapshot(
        self, owner_id: str, snapshot_id: str
    ) -> ArtifactProvenanceSnapshot | None: ...
    def list_artifact_refs(
        self, owner_id: str, snapshot_id: str
    ) -> Sequence[ArtifactProvenanceRef]: ...
    def get_claim(self, owner_id: str, claim_id: str) -> Claim | None: ...
    def list_claims(self, owner_id: str, snapshot_id: str) -> Sequence[Claim]: ...
    def list_citations(self, owner_id: str, claim_id: str) -> Sequence[Citation]: ...

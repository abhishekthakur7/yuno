"""Source, claim, citation, and generated-artifact provenance reads."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from yuno.api.contracts import (
    ArtifactProvenanceResponse,
    ArtifactSnapshotResponse,
    CitationResponse,
    ClaimResponse,
    SourceResponse,
)
from yuno.api.dependencies import get_owner_id, get_unit_of_work
from yuno.modules.learning_content.service import resolve_generation_context
from yuno.shared.domain.errors import NotFoundError
from yuno.shared.domain.hashing import hash_payload
from yuno.unit_of_work import SqlAlchemyUnitOfWork

router = APIRouter(tags=["provenance"])


def _source(s):
    return SourceResponse(**{k: v for k, v in s.__dict__.items() if k != "owner_id"})


def _claim(uow, owner_id, c):
    citations = []
    for x in uow.provenance.list_citations(owner_id, c.id):
        source = uow.provenance.get_source(owner_id, x.source_id)
        citations.append(
            CitationResponse(
                id=x.id,
                source=_source(source),
                source_snapshot_id=x.source_snapshot_id,
                locator=x.locator,
                support_kind=x.support_kind,
                note=x.note,
            )
        )
    return ClaimResponse(
        id=c.id,
        claim_text=c.claim_text,
        claim_type=c.claim_type,
        sensitive=c.sensitive,
        citations=citations,
    )


@router.get("/sources", response_model=list[SourceResponse])
def sources(
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_unit_of_work)],
):
    return [_source(x) for x in uow.provenance.list_sources(owner_id)]


@router.get("/sources/{source_id}", response_model=SourceResponse)
def source(
    source_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_unit_of_work)],
):
    value = uow.provenance.get_source(owner_id, source_id)
    if value is None:
        raise NotFoundError("The source was not found.")
    return _source(value)


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
def claim(
    claim_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_unit_of_work)],
):
    value = uow.provenance.get_claim(owner_id, claim_id)
    if value is None:
        raise NotFoundError("The claim was not found.")
    return _claim(uow, owner_id, value)


@router.get(
    "/artifacts/{artifact_id}/provenance", response_model=ArtifactProvenanceResponse
)
def artifact_provenance(
    artifact_id: str,
    request: Request,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_unit_of_work)],
):
    artifact = uow.learning_content.get_artifact(owner_id, artifact_id)
    if artifact is None or artifact.current_snapshot_id is None:
        raise NotFoundError("Artifact provenance was not found.")
    snapshot = uow.provenance.get_artifact_snapshot(
        owner_id, artifact.current_snapshot_id
    )
    refs = uow.provenance.list_artifact_refs(owner_id, snapshot.id)
    claims = uow.provenance.list_claims(owner_id, snapshot.id)
    baked = ArtifactSnapshotResponse(
        **{
            k: v
            for k, v in snapshot.__dict__.items()
            if k not in {"owner_id", "goal_id", "artifact_id", "attempt_id"}
        }
    )
    from yuno.modules.learning_content.domain import d3_cache_key_hash

    key_changed = False
    try:
        current_key, _, profile_hash, evidence_hash = resolve_generation_context(
            uow, owner_id, artifact.goal_id, artifact.topic_stable_id, artifact.layer
        )
        key_changed = d3_cache_key_hash(current_key) != artifact.cache_key_hash
    except NotFoundError:
        key_changed = True
        profile = uow.profiles_goals.get_profile(owner_id)
        profile_hash = hash_payload(
            {
                "experience": profile.experience if profile else None,
                "strengths": profile.strengths if profile else None,
                "weaknesses": profile.weaknesses if profile else None,
            }
        )
        evidence_hash = snapshot.evidence_state_hash
    adapter = request.app.state.generation_adapter
    current_hash = hash_payload(
        {
            "profile_hash": profile_hash,
            "evidence_state_hash": evidence_hash,
            "provider": getattr(adapter, "provider", snapshot.provider),
            "model": getattr(adapter, "model", snapshot.model),
            "schema": snapshot.schema_version,
            "contract": snapshot.contract_version,
        }
    )
    personalization_changed = current_hash != snapshot.snapshot_hash
    stale = personalization_changed or key_changed
    return ArtifactProvenanceResponse(
        artifact_id=artifact.id,
        baked_snapshot=baked,
        current_snapshot_hash=current_hash,
        stale=stale,
        stale_reasons=(["cache-key-changed"] if key_changed else [])
        + (["personalization-snapshot-mismatch"] if personalization_changed else []),
        refs=[{"kind": x.ref_kind, "reference_id": x.reference_id} for x in refs],
        claims=[_claim(uow, owner_id, x) for x in claims],
    )

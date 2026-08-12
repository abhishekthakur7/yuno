"""Source, claim, citation, and generated-artifact provenance reads."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from yuno.api.contracts import (
    ArtifactProvenanceResponse,
    ArtifactSnapshotResponse,
    CitationResponse,
    ClaimResponse,
    JobRefResponse,
    SourceResponse,
    SourceSnapshotResponse,
    accepted_job,
)
from yuno.api.dependencies import (
    get_job_dispatcher,
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
)
from yuno.modules.learning_content.service import resolve_generation_context
from yuno.modules.provenance.domain import SourceAvailability
from yuno.modules.provenance.service import (
    list_source_snapshots,
    reserve_source_retrieval,
)
from yuno.modules.provider.service import require_disclosure
from yuno.shared.application.jobs import JobDispatcher, JobLane, JobRequest
from yuno.shared.domain.errors import ConflictError, NotFoundError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id
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


@router.get(
    "/sources/{source_id}/snapshots",
    response_model=list[SourceSnapshotResponse],
)
def source_snapshots(
    source_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_unit_of_work)],
) -> list[SourceSnapshotResponse]:
    return [
        _source_snapshot(value)
        for value in list_source_snapshots(uow, owner_id, source_id)
    ]


@router.post(
    "/sources/{source_id}/retrieve",
    response_model=JobRefResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retrieve_source(
    source_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
) -> JSONResponse:
    prior = uow.provenance.get_retrieval_command_by_idempotency(owner_id, key)
    if prior is not None:
        command, _ = reserve_source_retrieval(
            uow, owner_id, source_id, key, prior.job_id
        )
        current = dispatcher.get(owner_id, command.job_id)
        if current is not None:
            return accepted_job(current)
    value = uow.provenance.get_source(owner_id, source_id)
    if value is None:
        raise NotFoundError("The source was not found.")
    if value.availability_status is SourceAvailability.WITHDRAWN:
        raise ConflictError("A withdrawn source cannot be retrieved.")
    disclosure = require_disclosure(
        uow,
        owner_id,
        category="source-retrieval",
        disclosure_version="source-network-v1",
    )
    command, _ = reserve_source_retrieval(uow, owner_id, source_id, key, new_id())
    uow.commit()
    return accepted_job(
        dispatcher.enqueue(
            JobRequest(
                "retrieve_source_snapshot",
                owner_id,
                {"source_id": source_id},
                dedupe_key=source_id,
                idempotency_key=key,
                requested_job_id=command.job_id,
                lane=JobLane.BACKGROUND,
                schema_version="source-snapshot-v1",
                request_ref=f"Source:{source_id}",
                disclosure_ref=disclosure.id,
            )
        )
    )


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


def _source_snapshot(value) -> SourceSnapshotResponse:
    return SourceSnapshotResponse(
        id=value.id,
        source_id=value.source_id,
        retrieved_at=value.retrieved_at,
        content_ref=value.content_ref,
        content_hash=value.content_hash,
        status=value.status,
        version_label=value.version_label,
    )


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
    adapter = request.app.state.provider_port
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

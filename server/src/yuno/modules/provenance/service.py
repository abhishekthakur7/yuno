"""Explicit source retrieval without implicit page-load network access."""

from __future__ import annotations

from yuno.modules.provenance.domain import (
    SourceAvailability,
    SourceRetrievalCommand,
    SourceRetrievalRequest,
    SourceRetrievalResult,
    SourceSnapshot,
)
from yuno.modules.provenance.ports import (
    ProvenanceUnitOfWork,
    SourceRetrievalAdapter,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    IdempotencyConflictError,
    NotFoundError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def list_source_snapshots(
    uow: ProvenanceUnitOfWork, owner_id: str, source_id: str
) -> tuple[SourceSnapshot, ...]:
    if uow.provenance.get_source(owner_id, source_id) is None:
        raise NotFoundError("The source was not found.")
    return tuple(uow.provenance.list_source_snapshots(owner_id, source_id))


def reserve_source_retrieval(
    uow: ProvenanceUnitOfWork,
    owner_id: str,
    source_id: str,
    idempotency_key: str,
    job_id: str,
) -> tuple[SourceRetrievalCommand, bool]:
    request_hash = hash_payload({"source_id": source_id})
    prior = uow.provenance.get_retrieval_command_by_idempotency(
        owner_id, idempotency_key
    )
    if prior is not None:
        if prior.request_hash != request_hash:
            raise IdempotencyConflictError(
                "The Idempotency-Key was reused for another source retrieval."
            )
        return prior, True
    source = uow.provenance.get_source(owner_id, source_id)
    if source is None:
        raise NotFoundError("The source was not found.")
    if source.availability_status is SourceAvailability.WITHDRAWN:
        raise ConflictError("A withdrawn source cannot be retrieved.")
    command = SourceRetrievalCommand(
        new_id(),
        owner_id,
        source_id,
        job_id,
        idempotency_key,
        request_hash,
        now_text(SystemClock()),
    )
    return uow.provenance.add_retrieval_command(command), False


def run_source_retrieval_job(
    request,
    uow_factory,
    adapter: SourceRetrievalAdapter,
) -> SourceSnapshot:
    source_id = str(request.payload["source_id"])
    with uow_factory() as uow:
        source = uow.provenance.get_source(request.owner_id, source_id)
        if source is None:
            raise NotFoundError("The source was not found.")
        if source.availability_status is SourceAvailability.WITHDRAWN:
            raise ConflictError("A withdrawn source cannot be retrieved.")
        if not source.canonical_url:
            raise DomainValidationError(
                "Source retrieval requires an approved canonical URL."
            )
        retrieval_request = SourceRetrievalRequest(
            owner_id=request.owner_id,
            source_id=source.id,
            canonical_url=source.canonical_url,
        )
    result = adapter.retrieve(retrieval_request)
    _validate_retrieval_result(result)
    snapshot = SourceSnapshot(
        id=new_id(),
        owner_id=request.owner_id,
        source_id=source_id,
        retrieved_at=result.retrieved_at,
        content_ref=result.content_ref,
        content_hash=result.content_hash,
        status=SourceAvailability.AVAILABLE.value,
        version_label=result.version_label,
    )
    with uow_factory() as uow:
        snapshot = uow.provenance.add_source_snapshot(snapshot)
        uow.commit()
        return snapshot


def _validate_retrieval_result(result: SourceRetrievalResult) -> None:
    if not isinstance(result, SourceRetrievalResult):
        raise DomainValidationError("Source retrieval returned an invalid result.")
    if not result.content_ref.strip() or not result.content_hash.strip():
        raise DomainValidationError(
            "Source retrieval must return a secure content reference and hash."
        )
    if not result.retrieved_at.strip():
        raise DomainValidationError("Source retrieval time must not be blank.")
    if result.version_label is not None and not result.version_label.strip():
        raise DomainValidationError("Source version labels must not be blank.")

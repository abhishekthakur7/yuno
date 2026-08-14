"""Explicit source retrieval without implicit page-load network access."""

from __future__ import annotations

from datetime import datetime, timedelta

from yuno.modules.provenance.adapters import purge_license_revoked_snapshot_bodies
from yuno.modules.provenance.domain import (
    Source,
    SourceAvailability,
    SourceRetrievalCommand,
    SourceRetrievalRequest,
    SourceRetrievalResult,
    SourceSnapshot,
    SourceWithdrawalReason,
)
from yuno.modules.provenance.ports import (
    ProvenanceUnitOfWork,
    SourceRetrievalAdapter,
)
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    IdempotencyConflictError,
    NotFoundError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

# IDK-003 §8/§10: automatic `unavailable` requires at least this many
# consecutive independent retrieval failures (with no intervening success)
# spanning at least this long, and never fewer/shorter.
_UNAVAILABLE_FAILURE_THRESHOLD = 3
_UNAVAILABLE_FAILURE_WINDOW = timedelta(hours=72)
# `source_snapshots.status` (provenance/models.py) admits 'failed' alongside
# the three SourceAvailability values; it has no matching domain enum member.
_FAILED_SNAPSHOT_STATUS = "failed"


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
    clock: Clock | None = None,
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
    try:
        result = adapter.retrieve(retrieval_request)
        _validate_retrieval_result(result)
    except Exception:
        _record_failed_retrieval(uow_factory, request.owner_id, source_id, clock)
        raise
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
        # IDK-003 §8: a successful retrieval automatically reverses an
        # `unavailable` source back to `available`; `withdrawn` is terminal
        # and is never reached here (guarded above).
        current = uow.provenance.get_source(request.owner_id, source_id)
        if (
            current is not None
            and current.availability_status is SourceAvailability.UNAVAILABLE
        ):
            uow.provenance.update_source(
                request.owner_id,
                source_id,
                now_text(clock or SystemClock()),
                {"availability_status": SourceAvailability.AVAILABLE},
            )
        uow.commit()
        return snapshot


def withdraw_source(
    uow_factory,
    owner_id: str,
    source_id: str,
    reason: SourceWithdrawalReason,
    *,
    superseded_by_source_id: str | None = None,
    clock: Clock | None = None,
) -> Source:
    """Withdraw a source in one transaction (IDK-003 §8 / §12 items 2 and 4).

    Sets `availability_status` to `withdrawn` and records `reason` as
    `withdrawal_reason`. `withdrawn` is terminal-for-new-use (§8/§11): a
    source that is already `withdrawn` is refused with `ConflictError`
    rather than transitioned again, mirroring the identical `WITHDRAWN`
    guard `reserve_source_retrieval`/`run_source_retrieval_job` above
    already use for the same enum value; nothing is written in that case.

    `reason in (LICENSE_REVOKED, LICENSE_CHANGED_INCOMPATIBLE)` is the only
    trigger for `purge_license_revoked_snapshot_bodies`
    (`provenance/adapters.py`): per §8, the other three reasons leave "the
    original storage grant ... never revoked", so a stored snapshot body
    must keep being available for audit/historical display and must never
    be purged for them.

    `superseded_by_source_id`, when given, is written in the same update
    as the status/reason change so replacement (§8 "Replacement", §12.2)
    is one status/reason/replacement write path rather than a second
    transition; lineage is always old -> new, exactly as the caller
    supplies it.
    """
    timestamp = now_text(clock or SystemClock())
    with uow_factory() as uow:
        source = uow.provenance.get_source(owner_id, source_id)
        if source is None:
            raise NotFoundError("The source was not found.")
        if source.availability_status is SourceAvailability.WITHDRAWN:
            raise ConflictError("A withdrawn source cannot be withdrawn again.")
        changes: dict[str, object] = {
            "availability_status": SourceAvailability.WITHDRAWN,
            "withdrawal_reason": reason,
        }
        if superseded_by_source_id is not None:
            changes["superseded_by_source_id"] = superseded_by_source_id
        updated = uow.provenance.update_source(owner_id, source_id, timestamp, changes)
        if updated is None:
            raise NotFoundError("The source was not found.")
        if reason in (
            SourceWithdrawalReason.LICENSE_REVOKED,
            SourceWithdrawalReason.LICENSE_CHANGED_INCOMPATIBLE,
        ):
            purge_license_revoked_snapshot_bodies(
                uow, owner_id=owner_id, source_id=source_id, now=timestamp
            )
        uow.commit()
        return updated


def _record_failed_retrieval(
    uow_factory, owner_id: str, source_id: str, clock: Clock | None
) -> None:
    """Persist a `failed` snapshot row and apply the §8 3-attempt/72h rule.

    The retrieval attempt log is the failure counter (IDK-003 §12.6): no
    separate counter column exists, so a failed attempt is recorded as an
    append-only `source_snapshots` row with `status = 'failed'`
    (`source_snapshots.status` CHECK admits `'failed'`,
    `provenance/models.py:87-89`; `SourceSnapshotBodyRow.redacted_failure`,
    `provenance/models.py:358`, already exists for such rows). A source only
    transitions to `unavailable` once the most recent consecutive run of
    `failed` snapshots (no intervening success) reaches
    `_UNAVAILABLE_FAILURE_THRESHOLD` entries AND spans at least
    `_UNAVAILABLE_FAILURE_WINDOW` from the earliest to the latest failure in
    that run — both conditions, never either alone (§10).
    """
    timestamp = now_text(clock or SystemClock())
    snapshot_id = new_id()
    failed_snapshot = SourceSnapshot(
        id=snapshot_id,
        owner_id=owner_id,
        source_id=source_id,
        retrieved_at=timestamp,
        content_ref=f"source-retrieval:failed:{snapshot_id}",
        content_hash=hash_payload(
            {"owner_id": owner_id, "source_id": source_id, "attempted_at": timestamp}
        ),
        status=_FAILED_SNAPSHOT_STATUS,
        version_label=None,
    )
    with uow_factory() as uow:
        uow.provenance.add_source_snapshot(failed_snapshot)
        # `add_source_snapshot` flushes the `SourceSnapshotRow` it adds but
        # not the `SourceSnapshotBodyRow` added right after it, and the
        # session factory runs with `autoflush=False`
        # (`shared/infrastructure/database.py:68`) — without an explicit
        # flush here, `list_source_snapshots` below would not see this
        # attempt's body row in the same transaction and would silently
        # drop it (`_source_snapshot` filters out any row without a body),
        # undercounting the streak by exactly the attempt just recorded.
        uow.session.flush()
        streak = _consecutive_failure_streak(
            uow.provenance.list_source_snapshots(owner_id, source_id)
        )
        if len(streak) >= _UNAVAILABLE_FAILURE_THRESHOLD and _spans_failure_window(
            streak
        ):
            current = uow.provenance.get_source(owner_id, source_id)
            # Only `available` -> `unavailable` is a real transition; a
            # source already `unavailable` stays as-is, and `withdrawn` is
            # terminal and unreachable here (the job refuses it up front).
            if (
                current is not None
                and current.availability_status is SourceAvailability.AVAILABLE
            ):
                uow.provenance.update_source(
                    owner_id,
                    source_id,
                    timestamp,
                    {"availability_status": SourceAvailability.UNAVAILABLE},
                )
        uow.commit()


def _consecutive_failure_streak(
    snapshots: tuple[SourceSnapshot, ...],
) -> list[SourceSnapshot]:
    """Return the most-recent run of `failed` snapshots, newest first.

    `snapshots` is already ordered newest-first
    (`SqlAlchemySourceRepository.list_source_snapshots`); a single successful
    (non-`failed`) snapshot breaks the streak, which is how reset-on-success
    happens automatically.
    """
    streak: list[SourceSnapshot] = []
    for snapshot in snapshots:
        if snapshot.status != _FAILED_SNAPSHOT_STATUS:
            break
        streak.append(snapshot)
    return streak


def _spans_failure_window(streak: list[SourceSnapshot]) -> bool:
    latest = datetime.fromisoformat(streak[0].retrieved_at)
    earliest = datetime.fromisoformat(streak[-1].retrieved_at)
    return (latest - earliest) >= _UNAVAILABLE_FAILURE_WINDOW


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

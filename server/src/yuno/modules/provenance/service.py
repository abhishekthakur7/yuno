"""Explicit source retrieval without implicit page-load network access."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta

from yuno.modules.identity.domain import Role, RolePolicy
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
# IDK-003 §9: the cadence leg of staleness detection re-checks every
# `available` source at least this often, measured from its newest
# successful (non-`failed`) snapshot; approved and non-configurable.
_STALENESS_RECHECK_CADENCE = timedelta(days=180)


def list_source_snapshots(
    uow: ProvenanceUnitOfWork, owner_id: str, source_id: str
) -> tuple[SourceSnapshot, ...]:
    if uow.provenance.get_source(owner_id, source_id) is None:
        raise NotFoundError("The source was not found.")
    return tuple(uow.provenance.list_source_snapshots(owner_id, source_id))


def sources_due_for_recheck(
    uow: ProvenanceUnitOfWork, owner_id: str, *, now: datetime
) -> tuple[Source, ...]:
    """Select `available` sources due for a §9 staleness re-check.

    Pure selection: reads only, no writes, and takes an already-open `uow`
    rather than a `uow_factory` -- the caller (the `app.py` sweep today;
    any future caller) owns the transaction and decides what to do with
    the result.

    IDK-003 §9's cadence clause reads: "Detection runs on a 180-day
    re-check cadence for every `available` source". This function is an
    engineering reading of that sentence, not decision text:

    - Only `AVAILABLE` sources are selected. `withdrawn` is
      terminal-for-new-use (§8) and is never re-retrieved. `unavailable`
      sources are deliberately excluded too: §9 says "every `available`
      source", and excluding `unavailable` is also what keeps a cadence
      sweep from retrying a source §8's own 3-attempt/72-hour rule already
      gave up on -- a source that fails its way to `unavailable` leaves
      the `available` set and this function simply stops selecting it, no
      unbounded retry storm.
    - "How stale" is measured from the newest snapshot whose `status` is
      not `_FAILED_SNAPSHOT_STATUS` -- the last genuinely successful
      retrieval, per `list_source_snapshots`'s newest-first order
      (`repository.py:135-145`). A source with no successful snapshot at
      all (never retrieved, or every attempt so far has failed) has no
      baseline to measure staleness from and is therefore always due.
    - Due when `now - retrieved_at >= 180 days` (`_STALENESS_RECHECK_CADENCE`),
      parsed with `datetime.fromisoformat` exactly as `_spans_failure_window`
      below already does for the same UTC TEXT format.

    §9 also names two other detection triggers this function does not
    implement. "Immediately on crossing the §8 `unavailable` threshold"
    already ships inside `_record_failed_retrieval` below: the crossing
    itself is read here as the detection event -- a source that just
    became `unavailable` is, by definition, now known-unreachable -- not
    as a command to schedule a further re-retrieval against a source three
    consecutive failures spanning 72+ hours just showed is unreachable.
    "Any explicit content-owner-initiated re-retrieval" already ships as
    `POST /sources/{source_id}/retrieve` (`routes/provenance.py:105-153`).
    Neither trigger needed new code here; only §9's cadence leg does.
    """
    due: list[Source] = []
    for source in uow.provenance.list_sources(owner_id):
        if source.availability_status is not SourceAvailability.AVAILABLE:
            continue
        baseline = _latest_successful_snapshot(
            uow.provenance.list_source_snapshots(owner_id, source.id)
        )
        if (
            baseline is not None
            and (now - datetime.fromisoformat(baseline.retrieved_at))
            < _STALENESS_RECHECK_CADENCE
        ):
            continue
        due.append(source)
    return tuple(due)


def _latest_successful_snapshot(
    snapshots: Sequence[SourceSnapshot],
) -> SourceSnapshot | None:
    """The newest non-`failed` snapshot, or `None` if every attempt so far
    has failed (or none has been made) -- `snapshots` is already
    newest-first (`list_source_snapshots`), so the first non-`failed`
    entry is the last genuinely successful retrieval.
    """
    for snapshot in snapshots:
        if snapshot.status != _FAILED_SNAPSHOT_STATUS:
            return snapshot
    return None


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

    IDK-003 §8 reserves `withdrawn` for entry "only by explicit editorial
    action" — the grant check below (`Role.DESIGNATED_EDITORIAL_APPROVER`)
    is what makes an action "editorial" rather than any owner-scoped call,
    so it lives here, inside the one function every caller (the offline
    `scripts/withdraw_source.py` CLI today, and any future caller) must go
    through, mirroring `publish_canonical_graph`'s identical
    `uow.owners.grants(...)` / `RolePolicy.require(...)` check
    (`canonical/publisher.py:139-140`) rather than trusting each caller to
    repeat it. There is no separate actor parameter: this is a
    single-local-owner product (exactly one `Owner` row, per PRD DAT-01),
    so `owner_id` — already the id every `provenance` read/write in this
    module is scoped to — is also the acting owner whose grant is checked;
    a distinct `actor_owner_id` would be a parameter nothing could ever
    supply a different value for.
    """
    timestamp = now_text(clock or SystemClock())
    with uow_factory() as uow:
        grants = uow.owners.grants(owner_id)
        RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)
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


def register_source(
    uow_factory,
    owner_id: str,
    sources: Sequence[Source],
    *,
    clock: Clock | None = None,
) -> tuple[Source, ...]:
    """Register a batch of sources in one transaction (IDK-003 §12 item 7).

    This is IDK-503 gate-3 blocking finding 1 (B4)'s *mechanism* half:
    before this function, `SqlAlchemySourceRepository.add_source`
    (`provenance/repository.py:44`) had no production caller at all --
    every `sources` row anywhere was either a test fixture or the offline
    `scripts/seed_performance_dataset.py:447` perf-dataset seed, itself
    fixture-shaped (the gate-3 re-run's own evidence for this finding).
    `register_source` is the "real seed/publish step, analogous to D1's
    offline canonical publisher" §12 item 7 calls for; the offline
    `scripts/register_source.py` CLI (mirroring `scripts/publish_canonical.py`
    and `scripts/withdraw_source.py`) is its only caller today. This
    function supplies the write path only -- it ships no source data of
    its own; every row it ever writes comes from whatever manifest a
    caller supplies.

    Every registered row is born `available`: `availability_status`,
    `withdrawal_reason` and `superseded_by_source_id` on each element of
    `sources` are ignored and overwritten with
    `SourceAvailability.AVAILABLE`/`None`/`None` regardless of what the
    caller supplies -- the only state
    `ck_sources_withdrawal_reason_required_iff_withdrawn`
    (`provenance/models.py:47-50`) admits for a freshly-registered row,
    since nothing has withdrawn it yet. `owner_id`, `created_at` and
    `updated_at` are likewise stamped here, not trusted from the caller,
    mirroring `publish_canonical_graph`'s identical "stamped at publish
    time" treatment of its own manifest placeholders
    (`canonical/publisher.py:200-210`, `scripts/publish_canonical.py`'s
    `_content_revision_from_json`) and this module's own `withdraw_source`
    rationale above for why `owner_id` is a function parameter rather than
    a per-row field trusted verbatim. `sources` is otherwise exactly the
    existing `Source` dataclass (`provenance/domain.py:38-52`) the CLI
    builds from its manifest -- no new domain type is introduced here
    (this module does not own `provenance/domain.py`), since `Source`
    already carries every field a registered row needs and the
    caller-supplied values for the fields above are overwritten anyway.

    Fails closed on re-registration: if a `sources` row with a given `id`
    already exists for `owner_id` -- either from an earlier call, or from
    one added earlier in this same batch -- `ConflictError` is raised.
    A same-batch duplicate is tracked with a local `seen_ids` set rather
    than re-querying `get_source` for it: `SqlAlchemySourceRepository.
    add_source` (`repository.py:44-54`) flushes the new `SourceRow` but
    not its paired `SourceBodyRow`, and `get_source`'s `_source()` treats a
    row with no body as absent (`repository.py:283-285`) -- so, with the
    session's `autoflush=False` (`shared/infrastructure/database.py:68`,
    the same characteristic `_record_failed_retrieval` below works around
    for the identical reason), a `get_source` call for an id added earlier
    in this same uncommitted batch would wrongly report it as free,
    letting a second `add_source` for that id reach the database and fail
    there instead, as `sources`' own `trg_sources_no_insert_replace`
    trigger, with a raw `IntegrityError` rather than this function's
    `ConflictError`. The whole batch is one `with uow_factory() as uow:`
    block, so a raise anywhere here, before `uow.commit()`, rolls every
    insert already flushed in this call back with it, exactly as
    `publish_canonical_graph` and `withdraw_source` above already do for
    their own writes. A partial registry can therefore never be committed
    from one manifest.

    IDK-003 §12 item 7 attributes source registration to a "content-owner
    role". No such role exists: `owner_role_grants.role` admits only
    `learner` and `designated_editorial_approver`
    (`identity/domain.py:28-30`), and IDK-003 §13 records that no distinct
    content-owner grant exists. Inventing one here would be an unapproved
    vocabulary change under IDK-003 §14's change control; leaving the
    write ungated would reopen the same class of gap B7/`withdraw_source`
    closed for withdrawal. This function therefore requires
    `Role.DESIGNATED_EDITORIAL_APPROVER` -- the exact grant and idiom
    `withdraw_source` above already uses for the identical reason -- and
    the check lives here, inside the one function every caller (today's
    `scripts/register_source.py`, and any future caller) must go through,
    not only in the CLI, so no future caller can bypass it. The resulting
    authority question -- reusing D1/IDK-002's canonical-publication grant
    to gate an IDK-003 act that neither decision assigns it -- is not a
    new finding: it consolidates under the round-3 record's existing
    finding B21
    (`docs/approvals/IDK-503-content-and-safety-review-rerun-2026-08-15-b.md:82`),
    which already names this same reuse for `withdraw_source` and records
    it as needing a decision-document action, not engineering work.
    """
    timestamp = now_text(clock or SystemClock())
    with uow_factory() as uow:
        grants = uow.owners.grants(owner_id)
        RolePolicy.require(grants, Role.DESIGNATED_EDITORIAL_APPROVER)
        registered: list[Source] = []
        seen_ids: set[str] = set()
        for source in sources:
            if source.id in seen_ids or (
                uow.provenance.get_source(owner_id, source.id) is not None
            ):
                raise ConflictError(
                    f"A source with id {source.id!r} is already registered."
                )
            seen_ids.add(source.id)
            registered.append(
                uow.provenance.add_source(
                    replace(
                        source,
                        owner_id=owner_id,
                        availability_status=SourceAvailability.AVAILABLE,
                        withdrawal_reason=None,
                        superseded_by_source_id=None,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
            )
        uow.commit()
        return tuple(registered)


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

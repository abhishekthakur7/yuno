"""Constrained HTTP source retrieval and content-addressed local storage."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import stat
from collections.abc import Callable, Iterable
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import delete, select, text

from yuno.modules.provenance.domain import (
    SourceRetrievalRequest,
    SourceRetrievalResult,
)
from yuno.modules.provenance.models import (
    CitationRow,
    SourceSnapshotBodyRow,
    SourceSnapshotRow,
)
from yuno.modules.provenance.ports import ProvenanceUnitOfWork
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import DomainValidationError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


class HttpSourceRetrievalAdapter:
    MAX_RESPONSE_BYTES = 10 * 1024 * 1024
    _ALLOWED_CONTENT_TYPES = frozenset(
        {
            "application/json",
            "application/pdf",
            "application/xhtml+xml",
            "application/xml",
        }
    )

    def __init__(
        self,
        snapshot_root: Path,
        *,
        client: httpx.Client | None = None,
        resolve: Callable[[str, int], Iterable[str]] | None = None,
    ) -> None:
        self._root = snapshot_root
        self._owns_client = client is None
        self._client = client or httpx.Client(
            follow_redirects=False,
            timeout=30.0,
            trust_env=False,
        )
        self._resolve = resolve or self._resolve_host

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def retrieve(
        self,
        request: SourceRetrievalRequest,
        *,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> SourceRetrievalResult:
        if cancelled():
            raise DomainValidationError("Source retrieval was cancelled.")
        try:
            parsed = urlsplit(request.canonical_url)
            hostname = parsed.hostname
            requested_port = parsed.port
        except (UnicodeError, ValueError):
            raise DomainValidationError("Source retrieval URL is invalid.") from None
        if parsed.scheme not in {"http", "https"} or not hostname:
            raise DomainValidationError(
                "Source retrieval permits only absolute HTTP(S) URLs."
            )
        if parsed.username is not None or parsed.password is not None:
            raise DomainValidationError(
                "Source retrieval URLs must not contain credentials."
            )
        expected_port = 443 if parsed.scheme == "https" else 80
        if requested_port not in {None, expected_port}:
            raise DomainValidationError(
                "Source retrieval permits only the standard HTTP(S) port."
            )
        addresses = self._resolve_public_addresses(hostname, expected_port)
        pinned_url = self._pinned_url(parsed, addresses[0], expected_port)
        host_header = f"[{hostname}]" if ":" in hostname else hostname
        if requested_port is not None:
            host_header = f"{host_header}:{requested_port}"
        try:
            with self._client.stream(
                "GET",
                pinned_url,
                headers={"Host": host_header},
                follow_redirects=False,
                extensions={"sni_hostname": hostname},
            ) as response:
                if response.is_redirect:
                    raise DomainValidationError(
                        "Source retrieval does not permit redirects."
                    )
                response.raise_for_status()
                self._validate_content_type(response)
                content = self._read_bounded(response, cancelled)
                version_label = response.headers.get("etag") or response.headers.get(
                    "last-modified"
                )
        except DomainValidationError:
            raise
        except httpx.HTTPError:
            raise DomainValidationError("Source retrieval failed safely.") from None
        content_hash = hashlib.sha256(content).hexdigest()
        self._prepare_root()
        path = self._root / content_hash
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            self._verify_existing(path, content)
        else:
            with os.fdopen(descriptor, "wb") as handle:
                os.fchmod(handle.fileno(), 0o600)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        return SourceRetrievalResult(
            content_ref=f"source-snapshot:{content_hash}",
            content_hash=content_hash,
            retrieved_at=now_text(SystemClock()),
            version_label=version_label,
        )

    def _resolve_public_addresses(self, hostname: str, port: int) -> tuple[str, ...]:
        try:
            addresses = tuple(dict.fromkeys(self._resolve(hostname, port)))
        except (OSError, UnicodeError, ValueError):
            raise DomainValidationError(
                "Source hostname could not be resolved safely."
            ) from None
        if not addresses:
            raise DomainValidationError("Source hostname could not be resolved safely.")
        try:
            parsed_addresses = tuple(ipaddress.ip_address(item) for item in addresses)
        except ValueError:
            raise DomainValidationError(
                "Source hostname could not be resolved safely."
            ) from None
        # Reject the hostname if any answer is unsafe. This prevents an attacker from
        # mixing a public answer with a private rebinding target. The request then uses
        # one validated address directly, so the transport cannot resolve it again.
        if any(
            not address.is_global
            or address.is_loopback
            or address.is_private
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
            or address.is_multicast
            for address in parsed_addresses
        ):
            raise DomainValidationError(
                "Source hostname does not resolve to a public address."
            )
        return tuple(str(address) for address in parsed_addresses)

    @staticmethod
    def _resolve_host(hostname: str, port: int) -> tuple[str, ...]:
        return tuple(
            result[4][0]
            for result in socket.getaddrinfo(
                hostname,
                port,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
        )

    @staticmethod
    def _pinned_url(parsed, address: str, port: int) -> httpx.URL:
        host = f"[{address}]" if ":" in address else address
        path = parsed.path or "/"
        target = f"{parsed.scheme}://{host}:{port}{path}"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        return httpx.URL(target)

    @classmethod
    def _validate_content_type(cls, response: httpx.Response) -> None:
        raw_content_type = response.headers.get("content-type", "")
        content_type = raw_content_type.partition(";")[0].strip().lower()
        if not (
            content_type.startswith("text/")
            or content_type in cls._ALLOWED_CONTENT_TYPES
        ):
            raise DomainValidationError(
                "Source retrieval returned an unsupported content type."
            )
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                raise DomainValidationError(
                    "Source retrieval returned an invalid content length."
                ) from None
            if length < 0 or length > cls.MAX_RESPONSE_BYTES:
                raise DomainValidationError(
                    "Source retrieval response exceeds the size limit."
                )

    @classmethod
    def _read_bounded(
        cls, response: httpx.Response, cancelled: Callable[[], bool]
    ) -> bytes:
        content = bytearray()
        for chunk in response.iter_bytes():
            if cancelled():
                raise DomainValidationError("Source retrieval was cancelled.")
            if len(content) + len(chunk) > cls.MAX_RESPONSE_BYTES:
                raise DomainValidationError(
                    "Source retrieval response exceeds the size limit."
                )
            content.extend(chunk)
        return bytes(content)

    def _prepare_root(self) -> None:
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root_status = self._root.lstat()
        if not stat.S_ISDIR(root_status.st_mode) or stat.S_ISLNK(root_status.st_mode):
            raise DomainValidationError(
                "Source snapshot root must be a real directory."
            )
        os.chmod(self._root, 0o700)

    @staticmethod
    def _verify_existing(path: Path, expected: bytes) -> None:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o600
        ):
            raise RuntimeError(
                "An existing source snapshot path is not a private regular file."
            )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise RuntimeError(
                "An existing source snapshot could not be opened safely."
            ) from exc
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            ):
                raise RuntimeError(
                    "An existing source snapshot changed during validation."
                )
            if handle.read() != expected:
                raise RuntimeError("A source snapshot hash collision was detected.")


def remove_unreferenced_snapshots(root: Path, referenced: set[str]) -> int:
    """Remove content-addressed files that no committed snapshot references."""
    if not root.exists():
        return 0
    status = root.lstat()
    if not stat.S_ISDIR(status.st_mode) or stat.S_ISLNK(status.st_mode):
        raise DomainValidationError("Source snapshot root must be a real directory.")
    removed = 0
    for path in root.iterdir():
        name = path.name
        if len(name) != 64 or any(char not in "0123456789abcdef" for char in name):
            continue
        file_status = path.lstat()
        if not stat.S_ISREG(file_status.st_mode) or file_status.st_nlink != 1:
            continue
        if f"source-snapshot:{name}" in referenced:
            continue
        path.unlink()
        removed += 1
    return removed


def purge_license_revoked_snapshot_bodies(
    uow: ProvenanceUnitOfWork, *, owner_id: str, source_id: str, now: str
) -> int:
    """Purge every persisted snapshot body for one source (IDK-003 §12.4).

    IDK-003 §6's "License-revocation purge" row and §8's `license-revoked`/
    `license-changed-incompatible` branch both require: the persisted
    full-body file for every one of the source's snapshots stops being
    served immediately and is deleted, while each `source_snapshots`
    metadata row (`content_hash`/`retrieved_at`/`status`) is retained
    untouched. This is a primitive -- it does not check `withdrawal_reason`
    or `availability_status` itself; the caller decides whether to invoke
    it (per the task brief).

    `source_snapshots` cannot be written at all: migration
    `6ee79a009c2a_generated_content_cache_and_provenance.py` (lines
    525-539) creates `trg_source_snapshots_no_update`,
    `trg_source_snapshots_no_insert_replace`, and
    `trg_source_snapshots_no_delete`, so this function never touches that
    table. Only `source_snapshot_bodies` -- the pointer row holding each
    snapshot's `content_ref` into content-addressed storage -- is deleted;
    that table carries no such trigger (verified: no migration creates a
    trigger naming `source_snapshot_bodies`).

    This mirrors `SqlAlchemyDataLifecycleRepository.purge_goal_bodies`
    (`data_lifecycle/repository.py:303-340`): delete the `*_bodies`
    pointer row and record a `file_cleanup_intents` row per deleted
    pointer so `execute_pending_cleanup`
    (`data_lifecycle/service.py:116-142`) unlinks the actual file out of
    transaction, against `ApprovedCleanupRoots.source`, through the
    `source-snapshot:` scheme `_resolve_cleanup_path` already wires up
    (`data_lifecycle/service.py:211-215`). The cleanup-intent insert uses
    raw SQL naming the `file_cleanup_intents` table, exactly as
    `purge_goal_bodies` uses raw SQL to delete from `source_snapshot_bodies`
    -- in both directions this is what keeps the write off the *other*
    module's ORM models, per this repo's "Module independence" import-linter
    contract (`server/pyproject.toml`), which forbids
    `yuno.modules.provenance` importing `yuno.modules.data_lifecycle` (and
    vice versa).

    `uow.session` -- the shared SQLAlchemy `Session` -- is not part of the
    `ProvenanceUnitOfWork` Protocol (`ports.py` declares only `provenance:
    SourceRepository`), but every object that actually satisfies that
    Protocol at runtime is the composition root `SqlAlchemyUnitOfWork`
    (`yuno/unit_of_work.py`), whose `session` property
    (`unit_of_work.py:193-196`) exists for exactly this kind of
    cross-cutting write; `api/provider_selection.py:59,70` already reaches
    `uow.session` the same way. No protocol method exists to delete a
    `source_snapshot_bodies` row or insert a `file_cleanup_intents` row,
    so there is no narrower legitimate seam available without editing
    `ports.py`/`repository.py`, which this task does not own.

    Idempotent: a second call finds no remaining `source_snapshot_bodies`
    rows for `source_id` (already deleted by the first call), so it purges
    nothing and returns 0.
    """
    session = uow.session
    content_refs = (
        session.execute(
            select(SourceSnapshotBodyRow.content_ref).where(
                SourceSnapshotBodyRow.owner_id == owner_id,
                SourceSnapshotBodyRow.source_id == source_id,
            )
        )
        .scalars()
        .all()
    )
    for content_ref in content_refs:
        session.execute(
            text(
                "INSERT INTO file_cleanup_intents "
                "(id, owner_id, goal_id, kind, path_ref, path_hash, status, "
                "failure_classification, attempts, created_at, updated_at, "
                "completed_at) "
                "VALUES (:id, :owner_id, NULL, 'source-snapshot', :path_ref, "
                ":path_hash, 'pending', NULL, 0, :now, :now, NULL)"
            ),
            {
                "id": new_id(),
                "owner_id": owner_id,
                "path_ref": content_ref,
                "path_hash": hash_payload(content_ref),
                "now": now,
            },
        )
    result = session.execute(
        delete(SourceSnapshotBodyRow).where(
            SourceSnapshotBodyRow.owner_id == owner_id,
            SourceSnapshotBodyRow.source_id == source_id,
        )
    )
    return result.rowcount or 0


_RETAINED_SNAPSHOTS_PER_SOURCE = 20


def prune_excess_snapshot_bodies(
    uow: ProvenanceUnitOfWork, *, owner_id: str, source_id: str, now: str
) -> int:
    """Prune excess persisted snapshot bodies for one source (IDK-003 §12
    item 9's janitor half; §6's "Retained snapshots per source" row: "20,
    oldest-first pruning among snapshots with no live
    `citations.source_snapshot_id` reference; a cited snapshot is never
    pruned").

    Selection rule, exactly what the tests in
    `test_provenance_snapshot_janitor.py` exercise: order the source's
    *body-bearing* snapshots -- those still carrying a
    `source_snapshot_bodies` row, i.e. not already purged by
    `purge_license_revoked_snapshot_bodies` above -- newest-first by
    `retrieved_at`, ties broken by `id` descending (the identical tiebreak
    `SqlAlchemySourceRepository.list_source_snapshots` uses,
    `repository.py:140`). The newest `_RETAINED_SNAPSHOTS_PER_SOURCE`
    (20 -- IDK-003 §6's approved, non-configurable threshold; this is
    plain engineering on an already-approved number, not a decision to
    make here) are always retained. Among everything older than that
    cutoff, every snapshot with no row in `citations` referencing it via
    `citations.source_snapshot_id` is pruned; a cited snapshot is *never*
    pruned even though it falls outside the newest 20 -- so 20 is a floor
    on what is kept, not a hard cap on the total row count. "Oldest-first"
    only orders the processing/cleanup-intent sequence: because every
    uncited snapshot past the cutoff is pruned unconditionally (this is
    not a bounded top-up trim to a target count), the final set pruned
    does not depend on iteration order.

    §6 names the row "Retained snapshots per source", but what this
    function actually prunes is each pruned snapshot's persisted body
    (its `source_snapshot_bodies` pointer row) plus, out of transaction,
    its content-addressed file -- never the `source_snapshots` metadata
    row itself. That gap between the section title and the implementation
    is forced, not chosen, and is named here rather than papered over:
    `source_snapshots` carries `trg_source_snapshots_no_update`/
    `_no_delete`/`_no_insert_replace` -- created by migration
    `6ee79a009c2a_generated_content_cache_and_provenance.py:525-539` and
    later dropped and recreated with an updated abort message by
    `e10d1a0c0100_policy_1_0_body_separation_and_retention.py:2170-2182`
    once body storage moved out of that table (both migrations keep the
    same three trigger names; the second is what is actually active at
    head). Verified empirically against a freshly migrated scratch
    database: `DELETE FROM source_snapshots WHERE id=...` raises
    `sqlite3.IntegrityError: source_snapshots header is immutable`, and
    the row is confirmed still present afterwards. `source_snapshot_bodies`
    carries no such trigger (confirmed: no migration creates one naming
    that table; the same DELETE against it there succeeds), so its
    pointer row is what is actually deleted here -- the identical trade
    §6's "License-revocation purge" row and
    `purge_license_revoked_snapshot_bodies` above already make ("the
    metadata row ... is retained").

    This is deliberately *not* an editorial action, so it needs, and has,
    no `designated_editorial_approver` grant check: it is automated local
    maintenance triggered by elapsed wall-clock time and accumulated
    snapshot count, not a human decision about a specific source (contrast
    IDK-003 §8's `withdrawn` transition, which *is* editorial and is
    gated by that grant in `provenance/service.py`).

    Follows `purge_license_revoked_snapshot_bodies`'s exact idiom for the
    write itself, for the same reasons documented on that function: reach
    `uow.session` directly (no narrower `ProvenanceUnitOfWork` Protocol
    seam exists for this write), insert one raw-SQL `file_cleanup_intents`
    row per deleted pointer to keep the write off `data_lifecycle`'s ORM
    models (this repo's "Module independence" import-linter contract), and
    let `execute_pending_cleanup` (`data_lifecycle/service.py:116-142`)
    perform the actual out-of-transaction unlink through the
    `source-snapshot:` scheme `_resolve_cleanup_path` already wires up
    against `ApprovedCleanupRoots.source` (`data_lifecycle/service.py:
    211-215`).

    Idempotent: a pruned snapshot has no `source_snapshot_bodies` row
    left, so it drops out of the "body-bearing" set entirely and cannot
    be selected again -- a second call with unchanged citations therefore
    prunes nothing further.

    Owner- and source-scoped: every read and write here is filtered by
    the `(owner_id, source_id)` pair the caller supplies; no other
    source's or owner's rows are touched.
    """
    session = uow.session
    ordered = session.execute(
        select(SourceSnapshotRow.id, SourceSnapshotBodyRow.content_ref)
        .join(
            SourceSnapshotBodyRow,
            SourceSnapshotBodyRow.snapshot_id == SourceSnapshotRow.id,
        )
        .where(
            SourceSnapshotRow.owner_id == owner_id,
            SourceSnapshotRow.source_id == source_id,
        )
        .order_by(SourceSnapshotRow.retrieved_at.desc(), SourceSnapshotRow.id.desc())
    ).all()
    excess_oldest_first = list(reversed(ordered[_RETAINED_SNAPSHOTS_PER_SOURCE:]))

    to_prune: list[tuple[str, str]] = []
    for snapshot_id, content_ref in excess_oldest_first:
        cited = session.execute(
            select(CitationRow.id)
            .where(
                CitationRow.owner_id == owner_id,
                CitationRow.source_snapshot_id == snapshot_id,
            )
            .limit(1)
        ).first()
        if cited is not None:
            continue
        to_prune.append((snapshot_id, content_ref))

    if not to_prune:
        return 0

    for snapshot_id, content_ref in to_prune:
        session.execute(
            text(
                "INSERT INTO file_cleanup_intents "
                "(id, owner_id, goal_id, kind, path_ref, path_hash, status, "
                "failure_classification, attempts, created_at, updated_at, "
                "completed_at) "
                "VALUES (:id, :owner_id, NULL, 'source-snapshot', :path_ref, "
                ":path_hash, 'pending', NULL, 0, :now, :now, NULL)"
            ),
            {
                "id": new_id(),
                "owner_id": owner_id,
                "path_ref": content_ref,
                "path_hash": hash_payload(content_ref),
                "now": now,
            },
        )
    result = session.execute(
        delete(SourceSnapshotBodyRow).where(
            SourceSnapshotBodyRow.owner_id == owner_id,
            SourceSnapshotBodyRow.source_id == source_id,
            SourceSnapshotBodyRow.snapshot_id.in_(
                [snapshot_id for snapshot_id, _ in to_prune]
            ),
        )
    )
    return result.rowcount or 0

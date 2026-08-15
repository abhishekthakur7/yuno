#!/usr/bin/env python3
"""The offline editorial CLI for production source registration (IDK-003
§12 item 7; IDK-503 gate 3 blocking finding 1 / B4 mechanism half).

Before this script, `register_source` (`yuno.modules.provenance.service`)
had no caller outside a test, and its underlying write primitive,
`SqlAlchemySourceRepository.add_source` (`provenance/repository.py:44`),
was called only by tests and by the offline
`scripts/seed_performance_dataset.py:447` perf-dataset seed -- itself
fixture-shaped, not a real registry-population path (gate-3 re-run
blocking finding 1's own evidence: `sqlite3 -readonly server/yuno.db
"SELECT count(*) FROM sources;"` returns `0`). §12 item 7 calls this out
by name: "Add a real production registry-population path -- a seed/publish
step, analogous to D1's offline canonical publisher, inserting `sources`
rows attributed to the content-owner role -- replacing the test-only
`add_source` call sites." This script is that step.

It is deliberately offline and non-HTTP -- no FastAPI import, no ASGI app,
no endpoint -- exactly the D1 offline canonical-publisher lane
(`scripts/publish_canonical.py`, spec §6.1) and the withdrawal lane this
project already shipped alongside it (`scripts/withdraw_source.py`, IDK-503
B7). An HTTP route would additionally require learner-facing copy this
project is forbidden to invent, and this script, like its two siblings,
carries none.

This script closes the *mechanism* only. It ships no source data of its
own: every row it ever writes comes from whatever manifest file the
operator supplies at run time. Which real sources to register, and under
what license basis, is content the content owner supplies and approves --
not an engineering decision, and nothing here bundles or defaults it.

**On attribution ("content-owner role").** §12 item 7 attributes
registration to a "content-owner role". No such role exists:
`owner_role_grants.role` admits only `learner` and
`designated_editorial_approver` (`yuno/modules/identity/domain.py:28-30`),
and IDK-003 §13 records that no distinct content-owner grant exists.
Inventing one here would be an unapproved vocabulary change under IDK-003
§14's change control; shipping this write path ungated would reopen the
same class of gap B7/`withdraw_source` already closed for withdrawal. This
script therefore requires `--actor-owner-id` to hold
`designated_editorial_approver`, the exact grant `withdraw_source` already
reuses for the identical reason -- and the resulting authority question
(reusing D1/IDK-002's canonical-publication grant to gate an IDK-003 act
that neither decision assigns it) is not a new finding: it consolidates
under the round-3 record's existing finding B21
(`docs/approvals/IDK-503-content-and-safety-review-rerun-2026-08-15-b.md:82`),
which already names this same reuse for `withdraw_source` and records it
as needing a decision-document action, not engineering work. The grant
check itself lives inside `register_source` (`provenance/service.py`), not
only here, so no future caller can bypass it -- this script's own job is
only `require_single_head` and manifest parsing, mirroring
`withdraw_source.py`'s identical division of labour.

Usage:

    uv run python scripts/register_source.py MANIFEST.json \\
        --actor-owner-id <owner id already holding the \\
            'designated_editorial_approver' grant> \\
        [--database-url sqlite+pysqlite:///./yuno.db]

`--database-url` defaults to `yuno.config.get_settings().database_url`,
resolved exactly once, right here -- that single resolved string builds
both the `Engine` passed to `require_single_head` and the session factory
the write transaction runs on, so the two can never silently target
different databases (mirrors `withdraw_source.py`'s and
`publish_canonical.py`'s identical rationale).

The manifest is a JSON object shaped:

    {
      "sources": [
        {
          "id": "...",
          "origin": "...",
          "source_type": "...",
          "title": "...",
          "publisher": "..." | null,        (optional, defaults to null)
          "canonical_url": "..." | null,     (optional, defaults to null)
          "license_status": "approved-open-license" | "approved-link-only"
        },
        ...
      ]
    }

A manifest-file-driven batch matches `publish_canonical.py`'s own shape
(`MANIFEST.json` as a positional argument, parsed by a `load_manifest`
function) -- §12 item 7 asks for a seed/publish *step*, and a batch of
sources is the natural unit of registration, one CLI invocation per batch
rather than one per source.

`license_status` is checked against exactly the two values
`ck_sources_license_status_valid` (`provenance/models.py:29-32`) admits --
`approved-open-license`, `approved-link-only` -- here, at parse time,
before any database call: an unrecognized value is a usage error (exit 2),
never forwarded to the service layer, the same way `withdraw_source.py`
rejects a bad `--reason`. This script does not resolve or render a named
license basis (IDK-003 §7 field 5) and does not branch retrieval on tier
(§12 item 3) -- both are explicitly out of scope for this change; the
`license_status` field itself is carried through unchanged because the
`sources` table's own CHECK constraint requires it on every row.

`availability_status`/`withdrawal_reason`/`superseded_by_source_id` are
not manifest fields at all: `register_source` always registers a source as
freshly `available` (see its own docstring) regardless of what a manifest
might claim, so there is nothing here to parse or validate for them.

Exit codes:
    0  registration succeeded; each registered source id is printed to
       stdout.
    1  a `YunoError` was raised anywhere before or during registration
       (Alembic not at head, the actor lacks the
       'designated_editorial_approver' grant, or a source id in the
       manifest is already registered) -- printed to stderr with its
       `code`, `message` and (if present) field errors / recovery action.
       Nothing is written to the database in this case: the whole batch is
       one transaction (`register_source`'s own docstring).
    2  a usage error: bad CLI arguments, a missing/unreadable manifest
       file, a manifest file that isn't valid JSON / doesn't match the
       expected shape, or an unrecognized `license_status` value.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from yuno.config import get_settings
from yuno.modules.provenance.domain import Source, SourceAvailability
from yuno.modules.provenance.service import register_source
from yuno.shared.domain.errors import YunoError
from yuno.shared.infrastructure.alembic_guard import require_single_head
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import create_unit_of_work_factory

# Matches `ck_sources_license_status_valid` (`provenance/models.py:29-32`)
# exactly. No Python enum exists for this field anywhere in the codebase
# (`provenance/domain.py`'s `Source.license_status` is a plain `str`), so
# this is the closed vocabulary checked against directly.
_VALID_LICENSE_STATUSES = ("approved-open-license", "approved-link-only")


def _source_from_json(entry: dict[str, Any]) -> Source:
    license_status = entry["license_status"]
    if license_status not in _VALID_LICENSE_STATUSES:
        raise ValueError(
            f"source {entry.get('id')!r} has license_status "
            f"{license_status!r}; expected one of: "
            + ", ".join(_VALID_LICENSE_STATUSES)
        )
    return Source(
        id=entry["id"],
        owner_id="",  # stamped with the real actor owner inside register_source
        origin=entry["origin"],
        source_type=entry["source_type"],
        title=entry["title"],
        publisher=entry.get("publisher"),
        canonical_url=entry.get("canonical_url"),
        license_status=license_status,
        availability_status=SourceAvailability.AVAILABLE,  # overwritten for real inside register_source
        withdrawal_reason=None,
        superseded_by_source_id=None,
        created_at="",  # stamped inside register_source
        updated_at="",  # stamped inside register_source
    )


def load_manifest(path: Path) -> tuple[Source, ...]:
    """Parse a manifest JSON file into `Source` objects ready for
    `register_source`.

    Every field register_source ignores and overwrites anyway
    (`owner_id`, `availability_status`, `withdrawal_reason`,
    `superseded_by_source_id`, `created_at`, `updated_at`) is filled with a
    placeholder here rather than left for the service to default, since
    `Source` is a frozen dataclass that requires a value for every field --
    see `register_source`'s own docstring for why those placeholders are
    safe to overwrite unconditionally.

    Raises `KeyError`/`json.JSONDecodeError`/`TypeError`/`ValueError` for a
    malformed file, including an unrecognized `license_status`; `main`
    turns any of those into exit code 2, not a stack trace.
    """
    raw = json.loads(path.read_text())
    entries = raw["sources"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest 'sources' must be a non-empty JSON array.")
    return tuple(_source_from_json(entry) for entry in entries)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register a batch of sources into the registry "
        "(IDK-003 §12 item 7, offline editorial tool)."
    )
    parser.add_argument("manifest", type=Path, help="Path to the manifest JSON file.")
    parser.add_argument(
        "--actor-owner-id",
        required=True,
        help="Owner id performing this registration; must already hold the "
        "'designated_editorial_approver' role grant.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL to register into (defaults to YUNO_DATABASE_URL / "
        "yuno.config.get_settings().database_url).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.manifest.exists():
        print(f"Manifest file not found: {args.manifest}", file=sys.stderr)
        return 2

    try:
        sources = load_manifest(args.manifest)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Manifest file {args.manifest} is malformed: {exc!r}", file=sys.stderr)
        return 2

    # Resolved exactly once (see module docstring); the engine and the
    # session factory both derive from this same string.
    database_url = args.database_url or get_settings().database_url
    engine = create_engine_for(database_url)
    try:
        try:
            # Before any session is opened, mirroring `withdraw_source.py`'s
            # and `publish_canonical_graph`'s identical ordering
            # (`canonical/publisher.py:117`).
            require_single_head(engine)
            session_factory = create_session_factory(engine)
            uow_factory = create_unit_of_work_factory(session_factory)

            registered = register_source(uow_factory, args.actor_owner_id, sources)
        except YunoError as exc:
            print(f"Registration failed: [{exc.code}] {exc.message}", file=sys.stderr)
            if exc.field_errors:
                for field_error in exc.field_errors:
                    print(f"  - {field_error}", file=sys.stderr)
            if exc.recovery_action:
                print(f"  recovery: {exc.recovery_action}", file=sys.stderr)
            return 1
    finally:
        engine.dispose()

    for source in registered:
        print(f"Registered source {source.id} ({source.license_status!r}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

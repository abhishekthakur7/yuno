#!/usr/bin/env python3
"""The offline editorial CLI for explicit source withdrawal (IDK-003 §8;
IDK-503 gate 3 blocking finding 4 / B7 remainder).

`withdraw_source` (`yuno.modules.provenance.service`) is IDK-003 §8's only
mechanism for entering `withdrawn`: "terminal-for-new-use, entered only by
explicit editorial action, never inferred from retrieval failures." Before
this script, nothing outside a test called it, so that action had no
running-product entry point and the license-revocation purge it gates
could never fire for real (IDK-503 gate-3 re-run, blocking finding 4).

This is that entry point, and it is deliberately offline and non-HTTP --
no FastAPI import, no ASGI app, no endpoint -- exactly the D1 offline
canonical-publisher lane (`scripts/publish_canonical.py`, spec §6.1):
IDK-003 §12 item 7 already frames the source-registry write path as "a
seed/publish step, analogous to D1's offline canonical publisher,"
attributed to the content-owner role, and withdrawal belongs in the same
lane. An HTTP route would additionally require learner-facing copy this
project is forbidden to invent, and a distinct content-owner role
vocabulary that IDK-003 §13 explicitly records does not exist and that
adding here would be an unapproved change under §14's change control --
neither gap is opened by this script.

Usage:

    uv run python scripts/withdraw_source.py SOURCE_ID \\
        --reason license-revoked \\
        --actor-owner-id <owner id already holding the \\
            'designated_editorial_approver' grant> \\
        [--superseded-by-source-id NEW_SOURCE_ID] \\
        [--database-url sqlite+pysqlite:///./yuno.db]

`--database-url` defaults to `yuno.config.get_settings().database_url`,
resolved exactly once, right here -- that single resolved string builds
both the `Engine` passed to `require_single_head` and the session factory
the write transaction runs on, so the two can never silently target
different databases (mirrors `publish_canonical.py`'s identical rationale,
same module).

`--reason` must be one of `SourceWithdrawalReason`'s five IDK-003 §11
values (`license-revoked`, `license-changed-incompatible`,
`publisher-retracted`, `factually-superseded`, `registry-declined`); an
unrecognized value is a usage error (exit 2), rejected here rather than
forwarded to the service layer.

The `designated_editorial_approver` grant is checked inside
`withdraw_source` itself, not only here (`provenance/service.py`) --
IDK-003 §8 makes holding that grant the substance of "explicit editorial
action", so it belongs in the one function every caller must go through,
not in this one caller alone. `--actor-owner-id` supplies the acting
owner: in this single-local-owner product that id is the same `owner_id`
every other `provenance` call already scopes reads/writes to (see
`withdraw_source`'s own docstring for why no separate actor parameter
exists).

`require_single_head(engine)` is checked here, before any session is
opened, mirroring `publish_canonical_graph`'s identical ordering
(`canonical/publisher.py:117`) -- `withdraw_source` takes a `uow_factory`,
not an `Engine`, so the migration guard is this script's job, same as the
grant check is `withdraw_source`'s.

Exit codes:
    0  withdrawal succeeded; the outcome is printed to stdout.
    1  a `YunoError` was raised anywhere before or during withdrawal
       (Alembic not at head, the source was not found, the source was
       already withdrawn, or the actor lacks the
       'designated_editorial_approver' grant) -- printed to stderr with its
       `code`, `message` and (if present) field errors / recovery action.
    2  a usage error: bad CLI arguments, or an unrecognized `--reason`
       value.
"""

from __future__ import annotations

import argparse
import sys

from yuno.config import get_settings
from yuno.modules.provenance.domain import SourceWithdrawalReason
from yuno.modules.provenance.service import withdraw_source
from yuno.shared.domain.errors import YunoError
from yuno.shared.infrastructure.alembic_guard import require_single_head
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import create_unit_of_work_factory


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Withdraw a source from the registry (IDK-003 §8, offline editorial tool)."
    )
    parser.add_argument("source_id", help="Id of the `sources` row to withdraw.")
    parser.add_argument(
        "--reason",
        required=True,
        help="One of SourceWithdrawalReason's five values (IDK-003 §11): "
        + ", ".join(reason.value for reason in SourceWithdrawalReason),
    )
    parser.add_argument(
        "--actor-owner-id",
        required=True,
        help="Owner id performing this withdrawal; must already hold the "
        "'designated_editorial_approver' role grant.",
    )
    parser.add_argument(
        "--superseded-by-source-id",
        default=None,
        help="Id of the replacement `sources` row (§8 'Replacement'), if any.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL to withdraw against (defaults to YUNO_DATABASE_URL / "
        "yuno.config.get_settings().database_url).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        reason = SourceWithdrawalReason(args.reason)
    except ValueError:
        print(
            f"--reason {args.reason!r} is not a valid SourceWithdrawalReason; "
            "expected one of: " + ", ".join(r.value for r in SourceWithdrawalReason),
            file=sys.stderr,
        )
        return 2

    # Resolved exactly once (see module docstring); the engine and the
    # session factory both derive from this same string.
    database_url = args.database_url or get_settings().database_url
    engine = create_engine_for(database_url)
    try:
        try:
            # Before any session is opened, mirroring
            # `publish_canonical_graph`'s ordering (see module docstring).
            require_single_head(engine)
            session_factory = create_session_factory(engine)
            uow_factory = create_unit_of_work_factory(session_factory)

            source = withdraw_source(
                uow_factory,
                args.actor_owner_id,
                args.source_id,
                reason,
                superseded_by_source_id=args.superseded_by_source_id,
            )
        except YunoError as exc:
            print(f"Withdrawal failed: [{exc.code}] {exc.message}", file=sys.stderr)
            if exc.field_errors:
                for field_error in exc.field_errors:
                    print(f"  - {field_error}", file=sys.stderr)
            if exc.recovery_action:
                print(f"  recovery: {exc.recovery_action}", file=sys.stderr)
            return 1
    finally:
        engine.dispose()

    outcome = f"Withdrew source {source.id} (reason: {reason.value!r})"
    if source.superseded_by_source_id:
        outcome += f", superseded by {source.superseded_by_source_id!r}."
    else:
        outcome += "."
    print(outcome)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""The offline rubric-manifest loader CLI (IDK-204 Scope,
`IMPLEMENTATION_TICKETS.md:1027`; IDK-503 gate 5's clearing line,
`docs/approvals/IDK-503-rerun-2026-08-15-b/gate-5-rubrics-scenarios.md:107`;
mechanism half of blocking finding B11).

`load_rubric_manifest` (`yuno.modules.evidence_evaluation.service`) is the
only path that ever writes a `rubrics`/`rubric_dimensions` header-and-six-
dimensions set. Before this script, nothing outside a test or
`scripts/seed_performance_dataset.py`'s synthetic fixture called
`uow.evidence.add_rubric` in a production shape, so a real, approved rubric
manifest had no running-product entry point (IDK-503 gate-5 re-run,
blocking finding B11: "`rubrics`/`rubric_dimensions` hold zero rows").

This is that entry point, and it is deliberately offline and non-HTTP --
no FastAPI import, no ASGI app, no endpoint -- the same D1 offline
canonical-publisher lane `scripts/publish_canonical.py` (spec §6.1) and
`scripts/withdraw_source.py` (IDK-003 §12 item 7) already use: rubric
manifest loading is exactly the same "seed/publish step... attributed to
the content-owner role" shape those two describe, and needs no HTTP route
of its own for the same two reasons neither of them does -- it would
require learner-facing copy this project is forbidden to invent, and a
distinct content-owner role vocabulary IDK-003 §13 explicitly records does
not exist and that adding here would be an unapproved change under §14's
change control.

This script closes only the mechanism half of B11. It ships no rubric
content: the three approved IDK-009 v1 manifests (`hands-on-rubric-v1`,
`practice-rubric-v1`, `mock-rubric-v1`) still need a content owner to
author them as manifest files before this loader can load them for real;
until then B11 stays open.

Usage:

    uv run python scripts/load_rubric_manifest.py MANIFEST.json \\
        --actor-owner-id <owner id already holding the \\
            'designated_editorial_approver' grant> \\
        [--database-url sqlite+pysqlite:///./yuno.db]

`--database-url` defaults to `yuno.config.get_settings().database_url`,
resolved exactly once, right here -- that single resolved string builds
both the `Engine` passed to `require_single_head` and the session factory
the write transaction runs on, so the two can never silently target
different databases (mirrors `withdraw_source.py`'s and
`publish_canonical.py`'s identical rationale, same module).

The manifest file is JSON shaped like:

    {
      "capability": "implement",
      "version": "v1",
      "role": null,
      "level": null,
      "status": "approved",
      "task_context": "...",
      "provenance": "...",
      "dimensions": [
        {
          "stable_dimension_id": "factual-and-mechanical-correctness",
          "name": "...",
          "description": "...",
          "ordinal": 1,
          "evaluation_guidance": "..."
        },
        ... exactly six entries ...
      ]
    }

`role`/`level` are optional (default `null`). Every other field is
required. This function performs no structural validation of its own --
`load_manifest` only parses JSON into placeholder `Rubric`/
`RubricDimension` domain objects (`id`/`owner_id`/`created_at`/
`rubric_id` left blank, stamped by `load_rubric_manifest` itself, mirroring
`publish_canonical.py`'s identical `Topic(graph_version_id="", ...)`
placeholder idiom) -- IDK-009 §6/§4 structural validation (exactly six
dimensions, ordinals 1..6, distinct stable ids, both critical stable
dimensions present) and the `status='approved'`/non-blank/version-gate
checks all live in `load_rubric_manifest` itself, not duplicated here, so
every caller gets the same guarantees.

The `designated_editorial_approver` grant is checked inside
`load_rubric_manifest` itself, not only here -- see that function's
docstring for why (it consolidates under existing finding B21 rather than
opening a new one). `--actor-owner-id` supplies the acting owner: in this
single-local-owner product that id is the same `owner_id` every
`evidence_evaluation` write is scoped to.

`require_single_head(engine)` is checked here, before any session is
opened, mirroring `withdraw_source.py`'s and `publish_canonical.py`'s
identical ordering -- `load_rubric_manifest` takes a `uow_factory`, not an
`Engine`, so the migration guard is this script's job, same as the grant
check is `load_rubric_manifest`'s.

Exit codes:
    0  the rubric was loaded; its id and capability/version are printed
       to stdout.
    1  a `YunoError` was raised anywhere before or during loading
       (Alembic not at head, the manifest failed IDK-009 §6/§4 structural
       validation, the manifest's status was not 'approved', the
       `(capability, version)` pair was already loaded, or the actor
       lacks the 'designated_editorial_approver' grant) -- printed to
       stderr with its `code`, `message` and (if present) field errors /
       recovery action. Nothing is written in this case.
    2  a usage error: bad CLI arguments, a missing/unreadable manifest
       file, or a manifest file that isn't valid JSON / doesn't match the
       expected shape (including an unrecognized `status` value).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from yuno.config import get_settings
from yuno.modules.evidence_evaluation.domain import (
    Rubric,
    RubricDimension,
    RubricStatus,
)
from yuno.modules.evidence_evaluation.service import load_rubric_manifest
from yuno.shared.domain.errors import YunoError
from yuno.shared.infrastructure.alembic_guard import require_single_head
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import create_unit_of_work_factory


def _rubric_from_json(payload: dict[str, Any]) -> Rubric:
    return Rubric(
        id="",  # stamped with a real id at load time
        owner_id="",  # stamped with --actor-owner-id at load time
        task_context=payload["task_context"],
        capability=payload["capability"],
        role=payload.get("role"),
        level=payload.get("level"),
        version=payload["version"],
        status=RubricStatus(payload["status"]),
        provenance=payload["provenance"],
        created_at="",  # stamped at load time
    )


def _dimension_from_json(payload: dict[str, Any]) -> RubricDimension:
    return RubricDimension(
        id="",  # stamped with a real id at load time
        rubric_id="",  # stamped with the rubric's real id at load time
        stable_dimension_id=payload["stable_dimension_id"],
        name=payload["name"],
        description=payload["description"],
        ordinal=payload["ordinal"],
        evaluation_guidance=payload["evaluation_guidance"],
    )


def load_manifest(path: Path) -> tuple[Rubric, tuple[RubricDimension, ...]]:
    """Parse a manifest JSON file into a placeholder `Rubric` plus its
    `RubricDimension`s -- see the module docstring for the expected shape.

    No IDK-009 §6/§4 structural validation happens here; that is entirely
    `load_rubric_manifest`'s job (see its docstring), so this function's
    only responsibility is turning JSON into the right domain shapes.

    Raises `KeyError`/`json.JSONDecodeError`/`TypeError`/`ValueError` for
    a malformed file, including a `status` value that isn't a valid
    `RubricStatus`; `main` turns any of those into exit code 2, not a
    stack trace.
    """
    raw = json.loads(path.read_text())
    dimensions = tuple(_dimension_from_json(item) for item in raw["dimensions"])
    rubric = _rubric_from_json(raw)
    return rubric, dimensions


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load one approved rubric manifest (IDK-204 Scope, offline tool)."
    )
    parser.add_argument("manifest", type=Path, help="Path to the manifest JSON file.")
    parser.add_argument(
        "--actor-owner-id",
        required=True,
        help="Owner id loading this manifest; must already hold the "
        "'designated_editorial_approver' grant.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL to load into (defaults to YUNO_DATABASE_URL / "
        "yuno.config.get_settings().database_url).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.manifest.exists():
        print(f"Manifest file not found: {args.manifest}", file=sys.stderr)
        return 2

    try:
        rubric, dimensions = load_manifest(args.manifest)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Manifest file {args.manifest} is malformed: {exc!r}", file=sys.stderr)
        return 2

    # Resolved exactly once (see module docstring); the engine and the
    # session factory both derive from this same string.
    database_url = args.database_url or get_settings().database_url
    engine = create_engine_for(database_url)
    try:
        try:
            # Before any session is opened, mirroring
            # `withdraw_source.py`'s / `publish_canonical.py`'s identical
            # ordering (see module docstring).
            require_single_head(engine)
            session_factory = create_session_factory(engine)
            uow_factory = create_unit_of_work_factory(session_factory)

            loaded = load_rubric_manifest(
                uow_factory, args.actor_owner_id, rubric, dimensions
            )
        except YunoError as exc:
            print(f"Load failed: [{exc.code}] {exc.message}", file=sys.stderr)
            if exc.field_errors:
                for field_error in exc.field_errors:
                    print(f"  - {field_error}", file=sys.stderr)
            if exc.recovery_action:
                print(f"  recovery: {exc.recovery_action}", file=sys.stderr)
            return 1
    finally:
        engine.dispose()

    print(
        f"Loaded rubric {loaded.id} (capability={loaded.capability!r}, "
        f"version={loaded.version!r})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

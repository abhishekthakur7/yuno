#!/usr/bin/env python3
"""The D1 offline canonical-graph publisher CLI (spec §6.1; IDK-102).

This is the *only* path that ever writes a `CanonicalGraphVersion` (D1
forbids in-app authoring/publication -- spec §5.1's `canonical` API
surface is read-only). It is offline and non-HTTP: no FastAPI import, no
ASGI app, no endpoint. Exit codes and stderr are its entire interface.

Usage:

    uv run python scripts/publish_canonical.py MANIFEST.json \\
        --actor-owner-id <owner id already holding the \\
            'designated_editorial_approver' grant> \\
        [--database-url sqlite+pysqlite:///./yuno.db]

`--database-url` defaults to `yuno.config.get_settings().database_url`,
resolved exactly once, right here -- that single resolved string builds
both the `Engine` passed to `require_single_head` and the session factory
the write transaction runs on, so the two can never silently target
different databases (an explicitly resolved URL always wins over ambient
settings picked up separately by two different code paths).

The manifest file is JSON shaped like `tests/fixtures/canonical/data/
*.json` -- `version_label`, `manifest_version`, `topics` (each carrying
its own `stable_slug`, used only for a topic's first-ever
`topic_identities` row), optional `relations`/`content_revisions`, and an
`approval` block naming `approver_role`/`basis_ref`. `manifest_hash` is
never read from the file -- it is always recomputed here via
`compute_manifest_hash`, exactly as `validate_manifest` independently
recomputes and compares it, so a stale or hand-edited hash can never
smuggle in an unvalidated shape.

Exit codes:
    0  published successfully; the version id is printed to stdout.
    1  a `YunoError` was raised anywhere before or during publish (Alembic
       not at head, manifest validation failure, missing
       'designated_editorial_approver' grant, or a reused version_label/
       manifest_hash) -- printed to stderr with its `code`, `message` and
       (for a validation failure) every violation, never just the first.
    2  a usage error: bad CLI arguments, a missing/unreadable manifest
       file, or a manifest file that isn't valid JSON / doesn't match the
       expected shape.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from yuno.config import get_settings
from yuno.modules.canonical.domain import (
    CanonicalGraphManifest,
    ContentRevision,
    RelationType,
    Topic,
    TopicRelation,
)
from yuno.modules.canonical.publisher import publish_canonical_graph
from yuno.modules.canonical.validation import compute_manifest_hash
from yuno.shared.domain.errors import YunoError
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import create_unit_of_work_factory


def _topic_from_json(payload: dict[str, Any]) -> Topic:
    return Topic(
        graph_version_id="",  # stamped with the real id at publish time
        stable_id=payload["stable_id"],
        title=payload["title"],
        subject=payload["subject"],
        scope_tags=tuple(payload["scope_tags"]),
        level_tag=payload["level_tag"],
        target_capability=payload["target_capability"],
        recommended_layer=payload["recommended_layer"],
        checkpoint_start=payload["checkpoint_start"],
        checkpoint_end=payload["checkpoint_end"],
    )


def _relation_from_json(payload: dict[str, Any]) -> TopicRelation:
    return TopicRelation(
        id=payload["id"],
        graph_version_id="",
        from_stable_id=payload["from_stable_id"],
        to_stable_id=payload["to_stable_id"],
        relation_type=RelationType(payload["relation_type"]),
        rationale=payload.get("rationale"),
    )


def _content_revision_from_json(payload: dict[str, Any]) -> ContentRevision:
    return ContentRevision(
        id=payload["id"],
        graph_version_id="",
        topic_stable_id=payload["topic_stable_id"],
        layer=payload["layer"],
        kind=payload["kind"],
        status=payload["status"],
        markdown_ref=payload["markdown_ref"],
        markdown_hash=payload["markdown_hash"],
        prompt_template_version=payload.get("prompt_template_version"),
        creator_owner_id="",  # stamped with actor_owner_id at publish time
        supersedes_revision_id=payload.get("supersedes_revision_id"),
        created_at="",  # stamped at publish time
    )


def load_manifest(path: Path) -> tuple[CanonicalGraphManifest, dict[str, str], str, str]:
    """Parse a manifest JSON file into a `CanonicalGraphManifest` plus
    everything `publish_canonical_graph` needs beyond it.

    Returns `(manifest, topic_identity_slugs, approver_role, basis_ref)`.
    Raises `KeyError`/`json.JSONDecodeError`/`TypeError` for a malformed
    file; `main` turns any of those into exit code 2, not a stack trace.
    """
    raw = json.loads(path.read_text())

    topics = tuple(_topic_from_json(t) for t in raw["topics"])
    relations = tuple(_relation_from_json(r) for r in raw.get("relations", []))
    content_revisions = tuple(
        _content_revision_from_json(c) for c in raw.get("content_revisions", [])
    )

    manifest_without_hash = CanonicalGraphManifest(
        version_label=raw["version_label"],
        manifest_version=raw["manifest_version"],
        manifest_hash="",
        topics=topics,
        relations=relations,
        content_revisions=content_revisions,
    )
    manifest = CanonicalGraphManifest(
        version_label=manifest_without_hash.version_label,
        manifest_version=manifest_without_hash.manifest_version,
        manifest_hash=compute_manifest_hash(manifest_without_hash),
        topics=topics,
        relations=relations,
        content_revisions=content_revisions,
    )

    topic_identity_slugs = {t["stable_id"]: t["stable_slug"] for t in raw["topics"]}

    approval = raw["approval"]
    return manifest, topic_identity_slugs, approval["approver_role"], approval["basis_ref"]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish a canonical curriculum graph manifest (D1 offline tool, spec §6.1)."
    )
    parser.add_argument("manifest", type=Path, help="Path to the manifest JSON file.")
    parser.add_argument(
        "--actor-owner-id",
        required=True,
        help="Owner id publishing this version; must already hold the "
        "'designated_editorial_approver' role grant.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL to publish into (defaults to YUNO_DATABASE_URL / "
        "yuno.config.get_settings().database_url).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.manifest.exists():
        print(f"Manifest file not found: {args.manifest}", file=sys.stderr)
        return 2

    try:
        manifest, topic_identity_slugs, approver_role, basis_ref = load_manifest(args.manifest)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Manifest file {args.manifest} is malformed: {exc!r}", file=sys.stderr)
        return 2

    if approver_role != "designated_editorial_approver":
        print(
            f"Manifest {args.manifest}'s approval.approver_role is "
            f"{approver_role!r}, expected 'designated_editorial_approver'.",
            file=sys.stderr,
        )
        return 2

    # Resolved exactly once (see module docstring); the engine and the
    # session factory both derive from this same string.
    database_url = args.database_url or get_settings().database_url
    engine = create_engine_for(database_url)
    try:
        session_factory = create_session_factory(engine)
        uow_factory = create_unit_of_work_factory(session_factory)

        try:
            version = publish_canonical_graph(
                engine=engine,
                uow_factory=uow_factory,  # type: ignore[arg-type]  # structural match, see publisher.py
                manifest=manifest,
                actor_owner_id=args.actor_owner_id,
                basis_ref=basis_ref,
                topic_identity_slugs=topic_identity_slugs,
            )
        except YunoError as exc:
            print(f"Publish failed: [{exc.code}] {exc.message}", file=sys.stderr)
            if exc.field_errors:
                for field_error in exc.field_errors:
                    print(f"  - {field_error}", file=sys.stderr)
            if exc.recovery_action:
                print(f"  recovery: {exc.recovery_action}", file=sys.stderr)
            return 1
    finally:
        engine.dispose()

    print(f"Published canonical graph version {version.id} ({version.version_label!r}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

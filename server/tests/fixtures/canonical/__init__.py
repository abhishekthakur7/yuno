"""Hand-authored MVP fixture data for the `canonical` module (spec §6.1
step 8), loaded into real `yuno.modules.canonical.domain` objects so
validation/publisher tests drive real data instead of hand-built dicts.

Every fixture is synthetic and explicitly labelled non-production --
IDK-001 (MVP curriculum spine) and IDK-002 (editorial approval evidence)
are both unresolved, so nothing here may ever be mistaken for approved
curriculum. Every `stable_id`/`title` carries a `fixture-`/`[SYNTHETIC]`
marker; `NON_PRODUCTION_LABEL` is attached to every loaded fixture as a
machine-readable flag a caller can assert on directly.

Fixture inventory (stops at the `CanonicalGraphManifest` + approval-
metadata level the current schema can express; `ports.py`/`repository.py`
/`service.py` are a later ticket):

- `v1_approved` / `v2_approved`: each a standalone, independently valid,
  independently publishable manifest. `v2_approved` carries forward
  three of v1's stable IDs unchanged (identity continuity across
  versions) and *drops* v1's `fixture-topic-gamma` while adding a new
  topic -- the canonical-graph half of the "upstream-deleted topic
  carrying local state" fixture the current schema can express (see
  "Honest gap" for the half it can't).
- `half_seeded`: a structurally valid manifest with no `approval` block
  (`.approval is None`) -- material present, no `EditorialApproval` row,
  per spec §6.1 step 6.
- `invalid_missing_stable_id`, `invalid_dangling_relation`,
  `invalid_prerequisite_cycle`, `invalid_out_of_boundary_subject`,
  `invalid_dsa_missing_scenario`, `invalid_go_node`: each engineered to
  trip exactly the one named `validation.ViolationCode` (see
  `EXPECTED_VIOLATIONS`), so a rollback test can assert both "rejected"
  and "rejected for the right reason".

Honest gap: spec §6.1 step 8 also names "an overlay conflict" and "an
upstream-deleted topic carrying local state" as their own fixtures. Both
require overlay/goal-local-state tables owned by IDK-104 (overlays) and
IDK-106 (goals), neither of which exists yet -- no overlay table, no
goal-local topic state, no "archived-local" record for a fixture to
attach to. `v2_approved`'s dropped `fixture-topic-gamma` is as far as the
current schema reaches toward the second fixture; nothing stands in for
"an overlay conflict" at all. IDK-104/106 own completing both.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from yuno.modules.canonical.domain import (
    CanonicalGraphManifest,
    ContentRevision,
    RelationType,
    Topic,
    TopicRelation,
)
from yuno.modules.canonical.validation import ViolationCode, compute_manifest_hash

_DATA_DIR = Path(__file__).parent / "data"

NON_PRODUCTION_LABEL = (
    "SYNTHETIC FIXTURE -- NOT PRODUCTION CURRICULUM (IDK-001/IDK-002 unresolved)"
)


@dataclass(frozen=True)
class ApprovalFixture:
    """Approval metadata a fixture carries pre-persistence. `basis_ref`
    and `approver_role` are the only fields a fixture can know ahead of
    time -- `id`, `graph_version_id`, `approver_owner_id` and
    `approved_at` only exist once a caller's own owner/version rows are
    inserted.
    """

    approver_role: str
    basis_ref: str


@dataclass(frozen=True)
class CanonicalFixture:
    """One loaded fixture: a ready-to-validate `CanonicalGraphManifest`
    plus everything a caller needs to drive it through the tables this
    manifest alone cannot represent.
    """

    name: str
    description: str
    non_production_label: str
    manifest: CanonicalGraphManifest
    # stable_id -> stable_slug, for a caller's own `create_topic_identity`
    # calls (`topic_identities` is a separate table from anything on
    # `CanonicalGraphManifest`/`Topic`).
    topic_identity_slugs: dict[str, str] = field(default_factory=dict)
    # `None` means "this fixture is deliberately half-seeded: no
    # `EditorialApproval` row should ever be recorded for it."
    approval: ApprovalFixture | None = None


CANONICAL_FIXTURE_NAMES: tuple[str, ...] = (
    "v1_approved",
    "v2_approved",
    "half_seeded",
    "invalid_missing_stable_id",
    "invalid_dangling_relation",
    "invalid_prerequisite_cycle",
    "invalid_out_of_boundary_subject",
    "invalid_dsa_missing_scenario",
    "invalid_go_node",
)

# Every invalid fixture's exact expected violation set, so a downstream
# test asserts both "rejected" and "rejected for the right reason".
# `invalid_go_node` deliberately trips two codes at once (defence in
# depth; see that fixture's `description`).
EXPECTED_VIOLATIONS: dict[str, frozenset[ViolationCode]] = {
    "invalid_missing_stable_id": frozenset({ViolationCode.MISSING_STABLE_ID}),
    "invalid_dangling_relation": frozenset({ViolationCode.DANGLING_RELATION_REFERENCE}),
    "invalid_prerequisite_cycle": frozenset({ViolationCode.PREREQUISITE_CYCLE}),
    "invalid_out_of_boundary_subject": frozenset({ViolationCode.OUT_OF_BOUNDARY_CURRICULUM_TAG}),
    "invalid_dsa_missing_scenario": frozenset({ViolationCode.DSA_TOPIC_MISSING_SCENARIO_RELATION}),
    "invalid_go_node": frozenset(
        {ViolationCode.GO_NODE_PRESENT, ViolationCode.OUT_OF_BOUNDARY_CURRICULUM_TAG}
    ),
}


def _topic_from_json(payload: dict, *, graph_version_id: str) -> Topic:
    return Topic(
        graph_version_id=graph_version_id,
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


def _relation_from_json(payload: dict, *, graph_version_id: str) -> TopicRelation:
    return TopicRelation(
        id=payload["id"],
        graph_version_id=graph_version_id,
        from_stable_id=payload["from_stable_id"],
        to_stable_id=payload["to_stable_id"],
        relation_type=RelationType(payload["relation_type"]),
        rationale=payload.get("rationale"),
    )


def _content_revision_from_json(payload: dict, *, graph_version_id: str) -> ContentRevision:
    """Builds a `ContentRevision` with fixture placeholders for fields
    that only exist once a caller's own owner/version rows are inserted
    (`graph_version_id`, `creator_owner_id`, `created_at`,
    `supersedes_revision_id`) -- a real caller replaces those via
    `dataclasses.replace(...)` before insert.
    """
    return ContentRevision(
        id=payload["id"],
        graph_version_id=graph_version_id,
        topic_stable_id=payload["topic_stable_id"],
        layer=payload["layer"],
        kind=payload["kind"],
        status=payload["status"],
        markdown_ref=payload["markdown_ref"],
        markdown_hash=payload["markdown_hash"],
        prompt_template_version=payload.get("prompt_template_version"),
        creator_owner_id="fixture-creator-owner-placeholder",
        supersedes_revision_id=None,
        created_at="1970-01-01T00:00:00Z",
    )


def load_fixture(name: str) -> CanonicalFixture:
    """Load one named fixture from `data/<name>.json` into a
    `CanonicalFixture`. Raises `KeyError` for an unknown name (see
    `CANONICAL_FIXTURE_NAMES`) and `FileNotFoundError` if the backing
    JSON file is missing -- both loud rather than returning `None`.
    """
    if name not in CANONICAL_FIXTURE_NAMES:
        raise KeyError(f"Unknown canonical fixture {name!r}; known: {CANONICAL_FIXTURE_NAMES}")

    raw = json.loads((_DATA_DIR / f"{name}.json").read_text())

    # Placeholder pre-persistence graph_version_id: excluded from
    # `compute_manifest_hash`'s payload (see validation.py), so any
    # stable placeholder is safe here -- the real id is only assigned
    # once a caller's own `create_version` runs.
    graph_version_id = f"fixture-graph-version-{name}"

    topics = tuple(_topic_from_json(t, graph_version_id=graph_version_id) for t in raw["topics"])
    relations = tuple(
        _relation_from_json(r, graph_version_id=graph_version_id) for r in raw.get("relations", [])
    )
    content_revisions = tuple(
        _content_revision_from_json(c, graph_version_id=graph_version_id)
        for c in raw.get("content_revisions", [])
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

    approval_payload = raw.get("approval")
    approval = (
        ApprovalFixture(
            approver_role=approval_payload["approver_role"],
            basis_ref=approval_payload["basis_ref"],
        )
        if approval_payload is not None
        else None
    )

    topic_identity_slugs = {t["stable_id"]: t["stable_slug"] for t in raw["topics"]}

    return CanonicalFixture(
        name=name,
        description=raw["description"],
        non_production_label=NON_PRODUCTION_LABEL,
        manifest=manifest,
        topic_identity_slugs=topic_identity_slugs,
        approval=approval,
    )


def list_fixture_names() -> tuple[str, ...]:
    return CANONICAL_FIXTURE_NAMES

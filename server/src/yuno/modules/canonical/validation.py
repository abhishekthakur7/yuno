"""Framework-free canonical-graph-manifest validation (spec §6.1 step 2).

Framework-free (spec §3.2) -- see `yuno.shared.domain`'s docstring for the
rule this module is bound by. Raises nothing: `validate_manifest` always
returns a `ValidationResult` listing every violation found, not just the
first -- a publisher operator needs the whole list. The caller (the
offline publisher) decides what to do with a non-empty result, typically
refusing to open a write transaction at all.

Curriculum boundary (CUR-01/CUR-02): `ALLOWED_SUBJECTS` below is the set
of category labels CUR-01/CUR-02 name directly in the PRD -- "Java/Spring
Boot microservices plus AWS and representative connected System
Design/RDB topics" (CUR-01) plus "DSA only where scenario-relevant"
(CUR-02). These are boundary categories, not curriculum content: no
specific topic id/title/relation appears here. Which topics within these
categories form the approved MVP spine is IDK-001, explicitly unresolved
-- this module enforces the boundary the PRD already states, nothing
more. "go"/"go_aws" are deliberately absent: CUR-02 defers Go+AWS to
Later, and `_validate_no_go_nodes` below enforces that as its own rule,
redundant with the general boundary check by design (defence in depth).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from yuno.modules.canonical.domain import (
    CanonicalGraphManifest,
    RelationType,
    Topic,
    TopicRelation,
)
from yuno.shared.domain.hashing import hash_payload

ALLOWED_SUBJECTS: frozenset[str] = frozenset(
    {
        "java",
        "spring_boot",
        "aws",
        "system_design",
        "rdb",
        "dsa",
    }
)

_GO_TOKENS: frozenset[str] = frozenset({"go", "golang", "go_aws"})

RELATION_TYPES_ALLOWED_TO_CYCLE: frozenset[RelationType] = frozenset(
    {RelationType.RELATED}
)
"""spec §4.3: "only explicitly configured non-prerequisite relation types
may cycle". `RELATED` is the one type this module configures as such --
every other relation type (including `SCENARIO`, which is not an
ordering relation but is not explicitly configured to cycle either)
participates in the DAG check below alongside `PREREQUISITE`."""


class ViolationCode(StrEnum):
    EMPTY_MANIFEST_VERSION = "empty_manifest_version"
    MANIFEST_HASH_MISMATCH = "manifest_hash_mismatch"
    MISSING_STABLE_ID = "missing_stable_id"
    DUPLICATE_STABLE_ID = "duplicate_stable_id"
    DANGLING_RELATION_REFERENCE = "dangling_relation_reference"
    DUPLICATE_RELATION_TUPLE = "duplicate_relation_tuple"
    PREREQUISITE_CYCLE = "prerequisite_cycle"
    OUT_OF_BOUNDARY_CURRICULUM_TAG = "out_of_boundary_curriculum_tag"
    DSA_TOPIC_MISSING_SCENARIO_RELATION = "dsa_topic_missing_scenario_relation"
    GO_NODE_PRESENT = "go_node_present"


@dataclass(frozen=True)
class Violation:
    code: ViolationCode
    message: str
    topic_stable_id: str | None = None
    relation_id: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    violations: tuple[Violation, ...]

    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0


def compute_manifest_hash(manifest: CanonicalGraphManifest) -> str:
    """The manifest hash a correctly-built `CanonicalGraphManifest` must
    carry as `manifest_hash`: a stable SHA-256 over `manifest_version` plus
    every topic/relation's identifying fields, deliberately excluding
    `manifest_hash` itself (hashing a value that includes its own hash is
    circular) and excluding `content_revisions` (immutable once inserted,
    identified by their own `markdown_hash`; not part of what the manifest
    hash pins).
    """
    payload = {
        "manifest_version": manifest.manifest_version,
        "version_label": manifest.version_label,
        "topics": sorted(
            (
                {
                    "stable_id": topic.stable_id,
                    "title": topic.title,
                    "subject": topic.subject,
                    "scope_tags": sorted(topic.scope_tags),
                    "level_tag": topic.level_tag,
                    "target_capability": topic.target_capability,
                    "recommended_layer": topic.recommended_layer,
                    "checkpoint_start": topic.checkpoint_start,
                    "checkpoint_end": topic.checkpoint_end,
                }
                for topic in manifest.topics
            ),
            key=lambda item: item["stable_id"],
        ),
        "relations": sorted(
            (
                {
                    "from_stable_id": relation.from_stable_id,
                    "to_stable_id": relation.to_stable_id,
                    "relation_type": relation.relation_type.value,
                }
                for relation in manifest.relations
            ),
            key=lambda item: (
                item["from_stable_id"],
                item["to_stable_id"],
                item["relation_type"],
            ),
        ),
    }
    return hash_payload(payload)


def validate_manifest(manifest: CanonicalGraphManifest) -> ValidationResult:
    """Validate `manifest` against every spec §6.1 step 2 rule this schema
    can express (stable IDs, curriculum tags, relationship references,
    prerequisite DAG, manifest version/hash, CUR-02's DSA-scenario and
    Go-absence rules). Returns every violation found; raises nothing.

    Deliberately not checked here, not silently skipped: layer/checkpoint
    content shape beyond the structural fields already on `Topic` (no
    separate layers table exists yet), and claim/citation shapes and
    source statuses, which belong to the `provenance` module (not yet
    built).
    """
    violations: list[Violation] = []
    violations.extend(_validate_manifest_identity(manifest))
    violations.extend(_validate_stable_ids(manifest.topics))
    violations.extend(_validate_relation_references(manifest))
    violations.extend(_validate_relation_cycles(manifest))
    violations.extend(_validate_curriculum_boundary(manifest.topics))
    violations.extend(_validate_no_go_nodes(manifest.topics))
    violations.extend(_validate_dsa_scenario_relations(manifest))
    return ValidationResult(violations=tuple(violations))


def _validate_manifest_identity(manifest: CanonicalGraphManifest) -> list[Violation]:
    violations: list[Violation] = []
    if not manifest.manifest_version.strip():
        violations.append(
            Violation(
                ViolationCode.EMPTY_MANIFEST_VERSION,
                "manifest_version must not be blank.",
            )
        )
    expected_hash = compute_manifest_hash(manifest)
    if manifest.manifest_hash != expected_hash:
        violations.append(
            Violation(
                ViolationCode.MANIFEST_HASH_MISMATCH,
                f"manifest_hash {manifest.manifest_hash!r} does not match the recomputed hash "
                f"{expected_hash!r} of the manifest's topics/relations.",
            )
        )
    return violations


def _validate_stable_ids(topics: tuple[Topic, ...]) -> list[Violation]:
    violations: list[Violation] = []
    seen: set[str] = set()
    for topic in topics:
        if not topic.stable_id.strip():
            violations.append(
                Violation(
                    ViolationCode.MISSING_STABLE_ID,
                    f"Topic {topic.title!r} has a missing/blank stable_id.",
                )
            )
            continue
        if topic.stable_id in seen:
            violations.append(
                Violation(
                    ViolationCode.DUPLICATE_STABLE_ID,
                    f"stable_id {topic.stable_id!r} appears on more than one topic.",
                    topic_stable_id=topic.stable_id,
                )
            )
        seen.add(topic.stable_id)
    return violations


def _validate_relation_references(manifest: CanonicalGraphManifest) -> list[Violation]:
    violations: list[Violation] = []
    known_stable_ids = {topic.stable_id for topic in manifest.topics}
    seen_tuples: set[tuple[str, str, str]] = set()
    for relation in manifest.relations:
        if relation.from_stable_id not in known_stable_ids:
            violations.append(
                Violation(
                    ViolationCode.DANGLING_RELATION_REFERENCE,
                    f"Relation {relation.id!r} references unknown from_stable_id "
                    f"{relation.from_stable_id!r}.",
                    relation_id=relation.id,
                )
            )
        if relation.to_stable_id not in known_stable_ids:
            violations.append(
                Violation(
                    ViolationCode.DANGLING_RELATION_REFERENCE,
                    f"Relation {relation.id!r} references unknown to_stable_id "
                    f"{relation.to_stable_id!r}.",
                    relation_id=relation.id,
                )
            )
        tuple_key = (
            relation.from_stable_id,
            relation.to_stable_id,
            relation.relation_type.value,
        )
        if tuple_key in seen_tuples:
            violations.append(
                Violation(
                    ViolationCode.DUPLICATE_RELATION_TUPLE,
                    f"Relation tuple {tuple_key!r} is duplicated (spec §4.3: unique tuple).",
                    relation_id=relation.id,
                )
            )
        seen_tuples.add(tuple_key)
    return violations


def _validate_relation_cycles(manifest: CanonicalGraphManifest) -> list[Violation]:
    """DAG check (spec §4.3): every relation type *except*
    `RELATION_TYPES_ALLOWED_TO_CYCLE` participates in one combined directed
    graph over topic stable IDs, which must have no cycle. Dangling
    references are skipped here (already reported by
    `_validate_relation_references`) so a bad reference doesn't also spam
    a spurious cycle violation.
    """
    known_stable_ids = {topic.stable_id for topic in manifest.topics}
    edges: dict[str, list[TopicRelation]] = defaultdict(list)
    for relation in manifest.relations:
        if relation.relation_type in RELATION_TYPES_ALLOWED_TO_CYCLE:
            continue
        if (
            relation.from_stable_id not in known_stable_ids
            or relation.to_stable_id not in known_stable_ids
        ):
            continue
        edges[relation.from_stable_id].append(relation)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(known_stable_ids, WHITE)
    cycle_relation: TopicRelation | None = None

    def visit(node: str) -> bool:
        nonlocal cycle_relation
        color[node] = GRAY
        for relation in edges.get(node, ()):
            neighbour = relation.to_stable_id
            if color[neighbour] == GRAY:
                cycle_relation = relation
                return True
            if color[neighbour] == WHITE and visit(neighbour):
                return True
        color[node] = BLACK
        return False

    for stable_id in known_stable_ids:
        if color[stable_id] == WHITE and visit(stable_id):
            break

    if cycle_relation is None:
        return []
    return [
        Violation(
            ViolationCode.PREREQUISITE_CYCLE,
            f"Relation {cycle_relation.id!r} ({cycle_relation.relation_type.value}) "
            f"participates in a cycle; only {sorted(t.value for t in RELATION_TYPES_ALLOWED_TO_CYCLE)} "
            "relation types may cycle.",
            relation_id=cycle_relation.id,
        )
    ]


def _validate_curriculum_boundary(topics: tuple[Topic, ...]) -> list[Violation]:
    violations: list[Violation] = []
    for topic in topics:
        if topic.subject not in ALLOWED_SUBJECTS:
            violations.append(
                Violation(
                    ViolationCode.OUT_OF_BOUNDARY_CURRICULUM_TAG,
                    f"Topic {topic.stable_id!r} has subject {topic.subject!r}, outside CUR-01's "
                    f"boundary {sorted(ALLOWED_SUBJECTS)}.",
                    topic_stable_id=topic.stable_id,
                )
            )
    return violations


def _validate_no_go_nodes(topics: tuple[Topic, ...]) -> list[Violation]:
    violations: list[Violation] = []
    for topic in topics:
        tokens = {topic.subject.lower(), *(tag.lower() for tag in topic.scope_tags)}
        if tokens & _GO_TOKENS:
            violations.append(
                Violation(
                    ViolationCode.GO_NODE_PRESENT,
                    f"Topic {topic.stable_id!r} is a Go node; CUR-02 defers Go+AWS to Later.",
                    topic_stable_id=topic.stable_id,
                )
            )
    return violations


def _validate_dsa_scenario_relations(
    manifest: CanonicalGraphManifest,
) -> list[Violation]:
    """CUR-02: a DSA topic (`subject == "dsa"`) requires at least one
    `SCENARIO` relation touching it, in either direction."""
    scenario_linked: set[str] = set()
    for relation in manifest.relations:
        if relation.relation_type is RelationType.SCENARIO:
            scenario_linked.add(relation.from_stable_id)
            scenario_linked.add(relation.to_stable_id)

    violations: list[Violation] = []
    for topic in manifest.topics:
        if topic.subject != "dsa":
            continue
        if topic.stable_id not in scenario_linked:
            violations.append(
                Violation(
                    ViolationCode.DSA_TOPIC_MISSING_SCENARIO_RELATION,
                    f"DSA topic {topic.stable_id!r} has no scenario relation (CUR-02).",
                    topic_stable_id=topic.stable_id,
                )
            )
    return violations

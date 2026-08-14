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

import json
from collections import defaultdict
from collections.abc import Sequence
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

    # -- basis_ref (IDK-002 §4) --------------------------------------------
    BASIS_REF_NOT_VALID_JSON = "basis_ref_not_valid_json"
    BASIS_REF_NOT_OBJECT = "basis_ref_not_object"
    BASIS_REF_UNKNOWN_FIELD = "basis_ref_unknown_field"
    BASIS_REF_MISSING_FIELD = "basis_ref_missing_field"
    BASIS_REF_INVALID_FIELD_TYPE = "basis_ref_invalid_field_type"
    BASIS_REF_BLANK_FIELD = "basis_ref_blank_field"
    BASIS_REF_COUNT_FIELD_INVALID = "basis_ref_count_field_invalid"
    BASIS_REF_REVIEWED_COUNT_MISMATCH = "basis_ref_reviewed_count_mismatch"
    BASIS_REF_VERSION_MISMATCH = "basis_ref_version_mismatch"
    BASIS_REF_POLICY_IDENTIFIER_MISMATCH = "basis_ref_policy_identifier_mismatch"
    BASIS_REF_MANIFEST_HASH_MISMATCH = "basis_ref_manifest_hash_mismatch"
    BASIS_REF_REVIEW_KIND_INVALID = "basis_ref_review_kind_invalid"
    BASIS_REF_REVIEW_KIND_PUBLISHED_STATE_MISMATCH = (
        "basis_ref_review_kind_published_state_mismatch"
    )
    BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID = (
        "basis_ref_diff_against_version_label_invalid"
    )
    BASIS_REF_DIFF_REVIEW_INVALID = "basis_ref_diff_review_invalid"


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


# --- basis_ref validation (IDK-002 §4) --------------------------------------

_BASIS_REF_VERSION_LITERAL = "editorial-approval-basis-v1"
"""IDK-002 §4 (`docs/decisions/IDK-002-editorial-approval-criteria.md:57`)."""

_POLICY_IDENTIFIER_LITERAL = "editorial-approval-criteria-v1"
"""IDK-002 §4 (`:58`)."""

_REVIEW_KINDS: frozenset[str] = frozenset({"initial", "diff"})
"""IDK-002 §4 (`:61`)."""


@dataclass(frozen=True)
class _CountedReviewSpec:
    """Shape of one of §4's nested `{result, *_reviewed, *_total}`-style
    review objects. `result_keys` are non-blank-string sub-fields;
    `count_pairs` are `(reviewed_key, total_key)` pairs that section 5
    requires to be equal (exhaustive review); `extra_count_keys` are
    non-negative-integer sub-fields with no equality requirement
    (`source_citation_review`'s live-check sample/population sizes,
    which section 5 samples rather than requiring exhaustive)."""

    field: str
    result_keys: tuple[str, ...]
    count_pairs: tuple[tuple[str, str], ...]
    extra_count_keys: tuple[str, ...] = ()


_COUNTED_REVIEW_SPECS: tuple[_CountedReviewSpec, ...] = (
    _CountedReviewSpec(
        "curriculum_boundary_review",
        ("result",),
        (("topics_reviewed", "topics_total"),),
    ),
    _CountedReviewSpec(
        "dsa_scenario_review",
        ("result",),
        (("dsa_topics_reviewed", "dsa_topics_total"),),
    ),
    _CountedReviewSpec(
        "dag_identity_review",
        ("result",),
        (("reused_stable_ids_confirmed", "reused_stable_ids_total"),),
    ),
    _CountedReviewSpec(
        "source_citation_review",
        ("structural_result", "live_check_result"),
        (("structural_claims_reviewed", "structural_claims_total"),),
        ("live_check_sample_size", "live_check_population_size"),
    ),
    _CountedReviewSpec(
        "layer_reversal_review", ("result",), (("topics_reviewed", "topics_total"),)
    ),
    _CountedReviewSpec("half_seed_immutability_check", ("result",), ()),
)
"""One spec per §4 nested review object except `diff_review`, which shares
`_DIFF_REVIEW_SPEC`'s shape but is validated separately because it is
nullable and conditional on `review_kind` rather than always required."""

_DIFF_REVIEW_SPEC = _CountedReviewSpec(
    "diff_review", ("result",), (("items_reviewed", "items_total"),)
)

_REQUIRED_TOP_LEVEL_FIELDS: frozenset[str] = frozenset(
    {
        "basis_ref_version",
        "policy_identifier",
        "reviewed_manifest_hash",
        "checklist_completed_at",
        "review_kind",
        "diff_against_version_label",
        "curriculum_boundary_review",
        "dsa_scenario_review",
        "dag_identity_review",
        "source_citation_review",
        "layer_reversal_review",
        "half_seed_immutability_check",
        "diff_review",
        "approver_is_sole_content_author",
    }
)
"""Every §4 field except `notes` (`:71`, the one optional field).
`diff_against_version_label`/`diff_review` are required *keys* even though
their value may legitimately be `null` -- §4 states both as `string | null`
respectively `{...} | null`, not "may be omitted"."""

_ALL_TOP_LEVEL_FIELDS: frozenset[str] = _REQUIRED_TOP_LEVEL_FIELDS | {"notes"}


def validate_basis_ref(
    basis_ref: str,
    *,
    manifest_hash: str,
    published_version_labels: Sequence[str] | None,
) -> ValidationResult:
    """Validate `basis_ref` against IDK-002 §4's `basis_ref` contract
    (`docs/decisions/IDK-002-editorial-approval-criteria.md:53-75`).
    Framework-free and raises nothing, matching `validate_manifest`'s
    contract: every violation found is accumulated and returned, except
    where a later check is impossible (unparseable JSON; a non-object
    payload; a field whose own type is wrong makes checking *its* value
    impossible, but does not stop other, independent fields from being
    checked).

    `manifest_hash` must already be the recomputed hash of the manifest
    being published (see `_validate_manifest_identity`), not a value
    trusted from the file, so the `reviewed_manifest_hash` cross-check
    below (§4 `:59`, `:73` item 3) binds the review to byte-identical
    published material.

    `published_version_labels` must be newest-first, exactly as
    `CanonicalGraphRepository.list_published_versions()` orders its rows
    (`repository.py:179-192`); an empty sequence means nothing has been
    published yet.

    `published_version_labels=None` means "published state is unknown to
    this caller" -- offline shape validation. It skips *only* the two §4
    rules that genuinely require database state: (1) `review_kind` must
    match whether a version is already published, and (2)
    `diff_against_version_label` must equal the actual latest published
    label. Every other §4 rule still runs, including the shape rules that
    need no database at all: when `review_kind == "diff"`,
    `diff_against_version_label` must still be non-null/non-blank and
    `diff_review` must still be a non-null object with equal counts; when
    `review_kind == "initial"`, both must still be null. A caller that
    passes `None` is responsible for the deferred published-state
    cross-check happening later, before any write --
    `publish_canonical_graph` does this by calling this same function
    again with the real `published_version_labels`.

    Deliberate gaps (decision is silent -- see this module's IDK-503
    task report, not invented here):
    - Nested `result`/`structural_result`/`live_check_result` sub-fields:
      §4 never states a value domain (no pass/fail enum given), so only
      "present, non-blank string" is enforced, not any particular enum.
    - `checklist_completed_at`: §4 says only "string, UTC timestamp"
      (`:60`) with no sub-format. No canonical UTC-timestamp *parser*
      exists in `yuno.shared.domain.clock` (only `utc_text`/`now_text`,
      which *produce* the stored format, not validate an arbitrary
      string against it), so only "non-blank string" is enforced here.
    - Count sub-fields (`*_reviewed`/`*_total`/`*_confirmed`/
      `*_sample_size`/`*_population_size`): §4 never types these
      explicitly; non-negative `int` is required here as an inference,
      with `bool` explicitly rejected (`isinstance(x, bool)` is a
      subtype of `int` in Python and must not silently count).
    - `approver_is_sole_content_author` is type-checked only (must be a
      `bool`); it is never cross-checked against actual authorship data,
      per §8's implementation items, which do not require that.
    """
    violations: list[Violation] = []
    try:
        parsed = json.loads(basis_ref)
    except json.JSONDecodeError as exc:
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_NOT_VALID_JSON,
                f"basis_ref is not valid JSON: {exc}",
            )
        )
        return ValidationResult(violations=tuple(violations))

    if not isinstance(parsed, dict):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_NOT_OBJECT,
                f"basis_ref must be a JSON object, got {type(parsed).__name__}.",
            )
        )
        return ValidationResult(violations=tuple(violations))

    for key in sorted(set(parsed) - _ALL_TOP_LEVEL_FIELDS):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_UNKNOWN_FIELD,
                f"basis_ref has unknown field {key!r}.",
            )
        )
    for field in sorted(_REQUIRED_TOP_LEVEL_FIELDS - set(parsed)):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_MISSING_FIELD,
                f"basis_ref is missing required field {field!r}.",
            )
        )

    basis_ref_version = _string_field(parsed, "basis_ref_version", violations)
    if (
        basis_ref_version is not None
        and basis_ref_version != _BASIS_REF_VERSION_LITERAL
    ):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_VERSION_MISMATCH,
                f"basis_ref_version must equal {_BASIS_REF_VERSION_LITERAL!r}, "
                f"got {basis_ref_version!r}.",
            )
        )

    policy_identifier = _string_field(parsed, "policy_identifier", violations)
    if (
        policy_identifier is not None
        and policy_identifier != _POLICY_IDENTIFIER_LITERAL
    ):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_POLICY_IDENTIFIER_MISMATCH,
                f"policy_identifier must equal {_POLICY_IDENTIFIER_LITERAL!r}, "
                f"got {policy_identifier!r}.",
            )
        )

    reviewed_manifest_hash = _string_field(parsed, "reviewed_manifest_hash", violations)
    if reviewed_manifest_hash is not None and reviewed_manifest_hash != manifest_hash:
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_MANIFEST_HASH_MISMATCH,
                f"reviewed_manifest_hash {reviewed_manifest_hash!r} does not match "
                f"manifest_hash {manifest_hash!r}.",
            )
        )

    # checklist_completed_at: non-blank string only -- see docstring's gap note.
    _string_field(parsed, "checklist_completed_at", violations)

    review_kind = _string_field(parsed, "review_kind", violations)
    if review_kind is not None and review_kind not in _REVIEW_KINDS:
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_REVIEW_KIND_INVALID,
                f'review_kind must be "initial" or "diff", got {review_kind!r}.',
            )
        )
        review_kind = None  # unknown value: conditional cross-checks below are moot.

    has_published = (
        published_version_labels is not None and len(published_version_labels) > 0
    )
    latest_label = published_version_labels[0] if has_published else None
    if review_kind is not None and published_version_labels is not None:
        expected_kind = "diff" if has_published else "initial"
        if review_kind != expected_kind:
            violations.append(
                Violation(
                    ViolationCode.BASIS_REF_REVIEW_KIND_PUBLISHED_STATE_MISMATCH,
                    f"review_kind {review_kind!r} does not match publish state "
                    f"({'a version is' if has_published else 'no version is'} already "
                    f"published); expected {expected_kind!r}.",
                )
            )

    diff_label_type_ok, diff_label_value = _nullable_string_field(
        parsed, "diff_against_version_label", violations
    )
    if diff_label_type_ok and review_kind == "diff":
        if diff_label_value is None or not diff_label_value.strip():
            violations.append(
                Violation(
                    ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID,
                    "diff_against_version_label must be a non-null, non-blank string "
                    'naming the latest published version when review_kind is "diff".',
                )
            )
        elif published_version_labels is not None and diff_label_value != latest_label:
            violations.append(
                Violation(
                    ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID,
                    f"diff_against_version_label {diff_label_value!r} must equal the "
                    f"latest published version label {latest_label!r}.",
                )
            )
    elif (
        diff_label_type_ok and review_kind == "initial" and diff_label_value is not None
    ):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_DIFF_AGAINST_VERSION_LABEL_INVALID,
                f'diff_against_version_label must be null when review_kind is "initial", '
                f"got {diff_label_value!r}.",
            )
        )

    for spec in _COUNTED_REVIEW_SPECS:
        obj = _required_object(parsed, spec.field, violations)
        if obj is not None:
            _validate_counted_review(obj, spec, violations)

    diff_review_type_ok, diff_review_obj = _nullable_object_field(
        parsed, "diff_review", violations
    )
    if diff_review_type_ok:
        if diff_review_obj is not None:
            _validate_counted_review(diff_review_obj, _DIFF_REVIEW_SPEC, violations)
        if review_kind == "diff" and diff_review_obj is None:
            violations.append(
                Violation(
                    ViolationCode.BASIS_REF_DIFF_REVIEW_INVALID,
                    'diff_review must be a non-null object when review_kind is "diff".',
                )
            )
        elif review_kind == "initial" and diff_review_obj is not None:
            violations.append(
                Violation(
                    ViolationCode.BASIS_REF_DIFF_REVIEW_INVALID,
                    'diff_review must be null when review_kind is "initial".',
                )
            )

    _bool_field(parsed, "approver_is_sole_content_author", violations)

    if "notes" in parsed and not isinstance(parsed["notes"], str):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_INVALID_FIELD_TYPE,
                f"basis_ref field 'notes' must be a string, got "
                f"{type(parsed['notes']).__name__}.",
            )
        )

    return ValidationResult(violations=tuple(violations))


def _string_field(parsed: dict, field: str, violations: list[Violation]) -> str | None:
    """Required non-blank string top-level field. Missing is not reported
    here -- the top-level required-field sweep already reports it."""
    if field not in parsed:
        return None
    value = parsed[field]
    if not isinstance(value, str):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_INVALID_FIELD_TYPE,
                f"basis_ref field {field!r} must be a string, got {type(value).__name__}.",
            )
        )
        return None
    if not value.strip():
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_BLANK_FIELD,
                f"basis_ref field {field!r} must not be blank.",
            )
        )
        return None
    return value


def _bool_field(parsed: dict, field: str, violations: list[Violation]) -> bool | None:
    if field not in parsed:
        return None
    value = parsed[field]
    if not isinstance(value, bool):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_INVALID_FIELD_TYPE,
                f"basis_ref field {field!r} must be a boolean, got {type(value).__name__}.",
            )
        )
        return None
    return value


def _nullable_string_field(
    parsed: dict, field: str, violations: list[Violation]
) -> tuple[bool, str | None]:
    """Returns `(type_ok, value)` for a required `string | null` field.
    `type_ok` is `False` only when the field is missing (already reported
    by the top-level sweep) or holds a value that is neither a string nor
    `null` -- callers must skip any dependent cross-check in that case."""
    if field not in parsed:
        return False, None
    value = parsed[field]
    if value is None:
        return True, None
    if not isinstance(value, str):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_INVALID_FIELD_TYPE,
                f"basis_ref field {field!r} must be a string or null, "
                f"got {type(value).__name__}.",
            )
        )
        return False, None
    return True, value


def _nullable_object_field(
    parsed: dict, field: str, violations: list[Violation]
) -> tuple[bool, dict | None]:
    """Returns `(type_ok, value)` for a required `object | null` field, same
    contract as `_nullable_string_field`."""
    if field not in parsed:
        return False, None
    value = parsed[field]
    if value is None:
        return True, None
    if not isinstance(value, dict):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_INVALID_FIELD_TYPE,
                f"basis_ref field {field!r} must be a JSON object or null, "
                f"got {type(value).__name__}.",
            )
        )
        return False, None
    return True, value


def _required_object(
    parsed: dict, field: str, violations: list[Violation]
) -> dict | None:
    """Required non-null object top-level field. Missing is not reported
    here -- the top-level required-field sweep already reports it."""
    if field not in parsed:
        return None
    value = parsed[field]
    if not isinstance(value, dict):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_INVALID_FIELD_TYPE,
                f"basis_ref field {field!r} must be a JSON object, got {type(value).__name__}.",
            )
        )
        return None
    return value


def _nested_string(
    obj: dict, parent_field: str, key: str, violations: list[Violation]
) -> str | None:
    if key not in obj:
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_MISSING_FIELD,
                f"basis_ref field {parent_field!r} is missing required key {key!r}.",
            )
        )
        return None
    value = obj[key]
    if not isinstance(value, str):
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_INVALID_FIELD_TYPE,
                f"basis_ref field {parent_field}.{key} must be a string, "
                f"got {type(value).__name__}.",
            )
        )
        return None
    if not value.strip():
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_BLANK_FIELD,
                f"basis_ref field {parent_field}.{key} must not be blank.",
            )
        )
        return None
    return value


def _nested_count(
    obj: dict, parent_field: str, key: str, violations: list[Violation]
) -> int | None:
    if key not in obj:
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_MISSING_FIELD,
                f"basis_ref field {parent_field!r} is missing required key {key!r}.",
            )
        )
        return None
    value = obj[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        violations.append(
            Violation(
                ViolationCode.BASIS_REF_COUNT_FIELD_INVALID,
                f"basis_ref field {parent_field}.{key} must be a non-negative integer, "
                f"got {value!r}.",
            )
        )
        return None
    return value


def _validate_counted_review(
    obj: dict, spec: _CountedReviewSpec, violations: list[Violation]
) -> None:
    for key in spec.result_keys:
        _nested_string(obj, spec.field, key, violations)
    for reviewed_key, total_key in spec.count_pairs:
        reviewed = _nested_count(obj, spec.field, reviewed_key, violations)
        total = _nested_count(obj, spec.field, total_key, violations)
        if reviewed is not None and total is not None and reviewed != total:
            violations.append(
                Violation(
                    ViolationCode.BASIS_REF_REVIEWED_COUNT_MISMATCH,
                    f"basis_ref field {spec.field}.{reviewed_key} ({reviewed}) must equal "
                    f"{spec.field}.{total_key} ({total}).",
                )
            )
    for key in spec.extra_count_keys:
        _nested_count(obj, spec.field, key, violations)

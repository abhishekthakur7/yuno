"""Unit tests for `yuno.modules.canonical.validation` (spec §6.1 step 2).

Every fixture stable ID/title/subject is synthetic (`fixture-topic-*`) --
no real Java/Spring/AWS/DSA topic content appears below, only the
boundary *categories* `validation.ALLOWED_SUBJECTS` encodes from
CUR-01/CUR-02.

No `hypothesis`-style generator is used (not a project dependency).
Table-driven coverage instead: each rule proven to fire on a manifest
engineered to violate it and to *not* fire on an otherwise-identical
valid manifest, plus one fully valid manifest exercising every rule's
happy path at once.
"""

from __future__ import annotations

from yuno.modules.canonical.domain import (
    CanonicalGraphManifest,
    ContentRevision,
    RelationType,
    Topic,
    TopicRelation,
)
from yuno.modules.canonical.validation import (
    ViolationCode,
    compute_manifest_hash,
    validate_manifest,
)


def _topic(
    stable_id: str,
    *,
    subject: str = "java",
    scope_tags: tuple[str, ...] = (),
    title: str | None = None,
) -> Topic:
    return Topic(
        graph_version_id="fixture-version-1",
        stable_id=stable_id,
        title=title or f"Fixture Topic {stable_id}",
        subject=subject,
        scope_tags=scope_tags,
        level_tag="fixture-level",
        target_capability="fixture-capability",
        recommended_layer="fixture-layer",
        checkpoint_start=0,
        checkpoint_end=1,
    )


def _relation(
    relation_id: str, from_stable_id: str, to_stable_id: str, relation_type: RelationType
) -> TopicRelation:
    return TopicRelation(
        id=relation_id,
        graph_version_id="fixture-version-1",
        from_stable_id=from_stable_id,
        to_stable_id=to_stable_id,
        relation_type=relation_type,
        rationale=None,
    )


def _manifest(
    topics: tuple[Topic, ...],
    relations: tuple[TopicRelation, ...] = (),
    *,
    manifest_version: str = "1",
    version_label: str = "fixture-graph-v1",
    hash_override: str | None = None,
) -> CanonicalGraphManifest:
    base = CanonicalGraphManifest(
        version_label=version_label,
        manifest_version=manifest_version,
        manifest_hash="",
        topics=topics,
        relations=relations,
    )
    manifest_hash = hash_override if hash_override is not None else compute_manifest_hash(base)
    return CanonicalGraphManifest(
        version_label=version_label,
        manifest_version=manifest_version,
        manifest_hash=manifest_hash,
        topics=topics,
        relations=relations,
    )


def _codes(result) -> set[ViolationCode]:
    return {violation.code for violation in result.violations}


# --- A fully valid manifest passes with zero violations. -------------------


def test_valid_manifest_has_no_violations() -> None:
    manifest = _manifest(
        topics=(
            _topic("fixture-topic-a", subject="java"),
            _topic("fixture-topic-b", subject="aws"),
            _topic("fixture-topic-dsa", subject="dsa"),
            _topic("fixture-topic-scenario", subject="system_design"),
        ),
        relations=(
            _relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.PREREQUISITE),
            _relation(
                "rel-2", "fixture-topic-dsa", "fixture-topic-scenario", RelationType.SCENARIO
            ),
        ),
    )
    result = validate_manifest(manifest)
    assert result.is_valid
    assert result.violations == ()


# --- Manifest version/hash validation. --------------------------------------


def test_blank_manifest_version_is_rejected() -> None:
    manifest = _manifest(topics=(_topic("fixture-topic-a"),), manifest_version="  ")
    result = validate_manifest(manifest)
    assert ViolationCode.EMPTY_MANIFEST_VERSION in _codes(result)


def test_manifest_hash_mismatch_is_rejected() -> None:
    manifest = _manifest(topics=(_topic("fixture-topic-a"),), hash_override="not-the-real-hash")
    result = validate_manifest(manifest)
    assert ViolationCode.MANIFEST_HASH_MISMATCH in _codes(result)


def test_manifest_hash_is_stable_for_reordered_but_equal_content() -> None:
    a = _topic("fixture-topic-a")
    b = _topic("fixture-topic-b")
    forward = CanonicalGraphManifest(
        version_label="v", manifest_version="1", manifest_hash="", topics=(a, b), relations=()
    )
    backward = CanonicalGraphManifest(
        version_label="v", manifest_version="1", manifest_hash="", topics=(b, a), relations=()
    )
    assert compute_manifest_hash(forward) == compute_manifest_hash(backward)


# --- Stable ID rules. --------------------------------------------------------


def test_missing_stable_id_is_rejected() -> None:
    manifest = _manifest(topics=(_topic(""),))
    result = validate_manifest(manifest)
    assert ViolationCode.MISSING_STABLE_ID in _codes(result)


def test_duplicate_stable_id_is_rejected() -> None:
    manifest = _manifest(
        topics=(
            _topic("fixture-topic-a", title="First"),
            _topic("fixture-topic-a", title="Second"),
        )
    )
    result = validate_manifest(manifest)
    assert ViolationCode.DUPLICATE_STABLE_ID in _codes(result)


def test_unique_stable_ids_are_not_flagged_as_duplicate() -> None:
    manifest = _manifest(topics=(_topic("fixture-topic-a"), _topic("fixture-topic-b")))
    result = validate_manifest(manifest)
    assert ViolationCode.DUPLICATE_STABLE_ID not in _codes(result)


# --- Relation reference/tuple rules. -----------------------------------------


def test_dangling_relation_reference_is_rejected() -> None:
    manifest = _manifest(
        topics=(_topic("fixture-topic-a"),),
        relations=(
            _relation("rel-1", "fixture-topic-a", "fixture-topic-missing", RelationType.PREREQUISITE),
        ),
    )
    result = validate_manifest(manifest)
    assert ViolationCode.DANGLING_RELATION_REFERENCE in _codes(result)


def test_relation_between_known_topics_has_no_dangling_reference_violation() -> None:
    manifest = _manifest(
        topics=(_topic("fixture-topic-a"), _topic("fixture-topic-b")),
        relations=(_relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.PREREQUISITE),),
    )
    result = validate_manifest(manifest)
    assert ViolationCode.DANGLING_RELATION_REFERENCE not in _codes(result)


def test_duplicate_relation_tuple_is_rejected() -> None:
    manifest = _manifest(
        topics=(_topic("fixture-topic-a"), _topic("fixture-topic-b")),
        relations=(
            _relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.PREREQUISITE),
            _relation("rel-2", "fixture-topic-a", "fixture-topic-b", RelationType.PREREQUISITE),
        ),
    )
    result = validate_manifest(manifest)
    assert ViolationCode.DUPLICATE_RELATION_TUPLE in _codes(result)


# --- Prerequisite-cycle / DAG rules. -----------------------------------------


def test_prerequisite_cycle_is_rejected() -> None:
    manifest = _manifest(
        topics=(_topic("fixture-topic-a"), _topic("fixture-topic-b"), _topic("fixture-topic-c")),
        relations=(
            _relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.PREREQUISITE),
            _relation("rel-2", "fixture-topic-b", "fixture-topic-c", RelationType.PREREQUISITE),
            _relation("rel-3", "fixture-topic-c", "fixture-topic-a", RelationType.PREREQUISITE),
        ),
    )
    result = validate_manifest(manifest)
    assert ViolationCode.PREREQUISITE_CYCLE in _codes(result)


def test_acyclic_prerequisite_chain_is_not_flagged() -> None:
    manifest = _manifest(
        topics=(_topic("fixture-topic-a"), _topic("fixture-topic-b"), _topic("fixture-topic-c")),
        relations=(
            _relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.PREREQUISITE),
            _relation("rel-2", "fixture-topic-b", "fixture-topic-c", RelationType.PREREQUISITE),
        ),
    )
    result = validate_manifest(manifest)
    assert ViolationCode.PREREQUISITE_CYCLE not in _codes(result)


def test_related_relation_type_is_explicitly_allowed_to_cycle() -> None:
    """spec §4.3: "only explicitly configured non-prerequisite relation
    types may cycle" -- `RELATED` is that configured type
    (`validation.RELATION_TYPES_ALLOWED_TO_CYCLE`)."""
    manifest = _manifest(
        topics=(_topic("fixture-topic-a"), _topic("fixture-topic-b")),
        relations=(
            _relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.RELATED),
            _relation("rel-2", "fixture-topic-b", "fixture-topic-a", RelationType.RELATED),
        ),
    )
    result = validate_manifest(manifest)
    assert ViolationCode.PREREQUISITE_CYCLE not in _codes(result)


def test_scenario_relation_type_still_participates_in_the_dag_check() -> None:
    """`SCENARIO` is not configured to allow cycles, so a scenario-only
    cycle is still rejected -- only `RELATED` is carved out."""
    manifest = _manifest(
        topics=(_topic("fixture-topic-a", subject="dsa"), _topic("fixture-topic-b", subject="dsa")),
        relations=(
            _relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.SCENARIO),
            _relation("rel-2", "fixture-topic-b", "fixture-topic-a", RelationType.SCENARIO),
        ),
    )
    result = validate_manifest(manifest)
    assert ViolationCode.PREREQUISITE_CYCLE in _codes(result)


# --- CUR-01 curriculum boundary. ---------------------------------------------


def test_out_of_boundary_subject_is_rejected() -> None:
    manifest = _manifest(topics=(_topic("fixture-topic-a", subject="astrology"),))
    result = validate_manifest(manifest)
    assert ViolationCode.OUT_OF_BOUNDARY_CURRICULUM_TAG in _codes(result)


def test_every_allowed_subject_passes_the_boundary_check() -> None:
    from yuno.modules.canonical.validation import ALLOWED_SUBJECTS

    for subject in ALLOWED_SUBJECTS:
        topics = (_topic("fixture-topic-a", subject=subject),)
        if subject == "dsa":
            # DSA topics need a scenario relation too (CUR-02) -- tested
            # separately below; give this one so only the boundary check
            # is exercised here.
            topics = topics + (_topic("fixture-topic-b", subject=subject),)
            relations = (
                _relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.SCENARIO),
            )
        else:
            relations = ()
        manifest = _manifest(topics=topics, relations=relations)
        result = validate_manifest(manifest)
        assert ViolationCode.OUT_OF_BOUNDARY_CURRICULUM_TAG not in _codes(result), subject


# --- CUR-02: DSA requires a scenario relation. -------------------------------


def test_dsa_topic_without_scenario_relation_is_rejected() -> None:
    manifest = _manifest(topics=(_topic("fixture-topic-a", subject="dsa"),))
    result = validate_manifest(manifest)
    assert ViolationCode.DSA_TOPIC_MISSING_SCENARIO_RELATION in _codes(result)


def test_dsa_topic_with_scenario_relation_is_accepted() -> None:
    manifest = _manifest(
        topics=(_topic("fixture-topic-a", subject="dsa"), _topic("fixture-topic-b", subject="system_design")),
        relations=(_relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.SCENARIO),),
    )
    result = validate_manifest(manifest)
    assert ViolationCode.DSA_TOPIC_MISSING_SCENARIO_RELATION not in _codes(result)


def test_dsa_topic_with_only_prerequisite_relation_is_still_rejected() -> None:
    """A non-scenario relation touching the DSA topic doesn't satisfy CUR-02."""
    manifest = _manifest(
        topics=(_topic("fixture-topic-a", subject="dsa"), _topic("fixture-topic-b", subject="java")),
        relations=(_relation("rel-1", "fixture-topic-a", "fixture-topic-b", RelationType.PREREQUISITE),),
    )
    result = validate_manifest(manifest)
    assert ViolationCode.DSA_TOPIC_MISSING_SCENARIO_RELATION in _codes(result)


# --- CUR-02: Go+AWS deferred -- any Go node is rejected. ---------------------


def test_go_subject_is_rejected() -> None:
    # "go" is also outside ALLOWED_SUBJECTS, so both checks fire --
    # defence in depth, per validation.py's module docstring.
    manifest = _manifest(topics=(_topic("fixture-topic-a", subject="go"),))
    result = validate_manifest(manifest)
    assert ViolationCode.GO_NODE_PRESENT in _codes(result)


def test_go_scope_tag_on_an_otherwise_valid_subject_is_rejected() -> None:
    manifest = _manifest(topics=(_topic("fixture-topic-a", subject="aws", scope_tags=("go",)),))
    result = validate_manifest(manifest)
    assert ViolationCode.GO_NODE_PRESENT in _codes(result)


def test_non_go_topic_has_no_go_node_violation() -> None:
    manifest = _manifest(topics=(_topic("fixture-topic-a", subject="java"),))
    result = validate_manifest(manifest)
    assert ViolationCode.GO_NODE_PRESENT not in _codes(result)


# --- Every violation is reported, not just the first (publisher-operator
# requirement from the IDK-102 task brief). ----------------------------------


def test_multiple_independent_violations_are_all_reported_together() -> None:
    manifest = _manifest(
        topics=(
            _topic("fixture-topic-a", subject="dsa"),  # missing scenario relation
            _topic("fixture-topic-b", subject="go"),  # go node + out of boundary
        ),
        relations=(
            _relation("rel-1", "fixture-topic-a", "fixture-topic-missing", RelationType.PREREQUISITE),
        ),
        hash_override="deliberately-wrong-hash",
    )
    result = validate_manifest(manifest)
    codes = _codes(result)
    assert ViolationCode.MANIFEST_HASH_MISMATCH in codes
    assert ViolationCode.DANGLING_RELATION_REFERENCE in codes
    assert ViolationCode.DSA_TOPIC_MISSING_SCENARIO_RELATION in codes
    assert ViolationCode.GO_NODE_PRESENT in codes
    assert ViolationCode.OUT_OF_BOUNDARY_CURRICULUM_TAG in codes
    assert len(result.violations) >= 5


# --- Domain dataclasses used but not exercised above: a smoke test that
# `ContentRevision` (part of `CanonicalGraphManifest`) round-trips through
# construction without affecting validation (out of this ticket's
# validated-rule set -- see `validate_manifest`'s docstring). -----------------


def test_content_revisions_do_not_affect_validation_result() -> None:
    revision = ContentRevision(
        id="fixture-revision-1",
        graph_version_id="fixture-version-1",
        topic_stable_id="fixture-topic-a",
        layer="fixture-layer",
        kind="fixture-kind",
        status="published",
        markdown_ref="fixture-ref",
        markdown_hash="fixture-hash",
        prompt_template_version=None,
        creator_owner_id="fixture-owner",
        supersedes_revision_id=None,
        created_at="2026-01-01T00:00:00.000000Z",
    )
    without = _manifest(topics=(_topic("fixture-topic-a"),))
    with_revision = CanonicalGraphManifest(
        version_label=without.version_label,
        manifest_version=without.manifest_version,
        manifest_hash=without.manifest_hash,
        topics=without.topics,
        relations=without.relations,
        content_revisions=(revision,),
    )
    assert validate_manifest(without) == validate_manifest(with_revision)

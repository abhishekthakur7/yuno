"""Integration tests for the offline publisher
(`yuno.modules.canonical.publisher.publish_canonical_graph`, spec §6.1
steps 1-7).

Covers: a valid, approved publish persists everything (version, topic
identities, topics, relations, content revisions, approval, one audit
event) and becomes readable through the approval-gated reads; a manifest
that fails `validate_manifest`, or an actor missing the editorial grant,
is rejected before any row is written; a mid-transaction constraint
violation rolls back everything flushed earlier in the same transaction;
and republishing under a reused `version_label`/`manifest_hash` is
rejected (step 7), with the already-published version still immutable.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError

from tests.fixtures.canonical import load_fixture
from yuno.modules.canonical.domain import CanonicalGraphManifest, ContentRevision, Topic
from yuno.modules.canonical.models import (
    CanonicalGraphVersionRow,
    ContentRevisionRow,
    EditorialApprovalRow,
    TopicIdentityRow,
    TopicRelationRow,
    TopicRow,
)
from yuno.modules.canonical.publisher import publish_canonical_graph
from yuno.modules.canonical.validation import compute_manifest_hash
from yuno.modules.identity.domain import Role
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    RoleNotGrantedError,
)

_CANONICAL_TABLES = (
    CanonicalGraphVersionRow,
    TopicIdentityRow,
    TopicRow,
    TopicRelationRow,
    ContentRevisionRow,
    EditorialApprovalRow,
)


def _row_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            model.__tablename__: connection.execute(
                select(func.count()).select_from(model)
            ).scalar_one()
            for model in _CANONICAL_TABLES
        }


def _assert_canonical_tables_empty(engine: Engine) -> None:
    counts = _row_counts(engine)
    assert all(count == 0 for count in counts.values()), counts


def _basis_ref_payload(
    *,
    manifest_hash: str,
    review_kind: str = "initial",
    diff_against_version_label: str | None = None,
) -> str:
    """A minimal, fully valid IDK-002 §4 `basis_ref` JSON string for tests
    below that need `validate_basis_ref` to pass cleanly so they can
    exercise something else entirely (a mid-transaction DB failure, a
    version_label/manifest_hash conflict) without that unrelated
    mechanism being masked by a basis_ref rejection. Not a checklist
    fixture in its own right -- `v1_approved.json`/`v2_approved.json`
    (`tests/fixtures/canonical/data/`) are that; this covers the shape
    with all-zero review counts, which `validate_basis_ref` accepts
    (reviewed == total, no cross-check against the manifest's real
    topic/relation counts).
    """
    diff_review = (
        {"result": "pass", "items_reviewed": 0, "items_total": 0}
        if review_kind == "diff"
        else None
    )
    payload = {
        "basis_ref_version": "editorial-approval-basis-v1",
        "policy_identifier": "editorial-approval-criteria-v1",
        "reviewed_manifest_hash": manifest_hash,
        "checklist_completed_at": "2026-01-01T00:00:00Z",
        "review_kind": review_kind,
        "diff_against_version_label": diff_against_version_label,
        "curriculum_boundary_review": {
            "result": "pass",
            "topics_reviewed": 0,
            "topics_total": 0,
        },
        "dsa_scenario_review": {
            "result": "pass",
            "dsa_topics_reviewed": 0,
            "dsa_topics_total": 0,
        },
        "dag_identity_review": {
            "result": "pass",
            "reused_stable_ids_confirmed": 0,
            "reused_stable_ids_total": 0,
        },
        "source_citation_review": {
            "structural_result": "pass",
            "live_check_result": "pass",
            "structural_claims_reviewed": 0,
            "structural_claims_total": 0,
            "live_check_sample_size": 0,
            "live_check_population_size": 0,
        },
        "layer_reversal_review": {
            "result": "pass",
            "topics_reviewed": 0,
            "topics_total": 0,
        },
        "half_seed_immutability_check": {"result": "pass"},
        "diff_review": diff_review,
        "approver_is_sole_content_author": True,
        "notes": "SYNTHETIC FIXTURE basis_ref -- mechanism test only, not a real editorial review.",
    }
    return json.dumps(payload)


@pytest.fixture
def approver_owner_id(uow_factory: UnitOfWorkFactory) -> str:
    """A local owner holding `designated_editorial_approver`, granted
    explicitly here (rather than via `ensure_local_owner`) so the fixture
    states exactly which grant the test relies on.
    """
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Fixture Approver")
        uow.owners.grant_role(
            owner.id, Role.DESIGNATED_EDITORIAL_APPROVER, assigned_by_owner_id=owner.id
        )
        uow.commit()
    return owner.id


@pytest.fixture
def learner_only_owner_id(uow_factory: UnitOfWorkFactory) -> str:
    """A local owner holding only `Role.LEARNER` -- spec §6.1 step 3's
    negative case.
    """
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Fixture Learner")
        uow.owners.grant_role(owner.id, Role.LEARNER, assigned_by_owner_id=owner.id)
        uow.commit()
    return owner.id


# ---------------------------------------------------------------------------
# Happy path: a valid, approved manifest actually publishes.
# ---------------------------------------------------------------------------


def test_publish_persists_version_topics_relations_content_and_approval(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    fixture = load_fixture("v1_approved")
    assert fixture.approval is not None

    version = publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=fixture.manifest,
        actor_owner_id=approver_owner_id,
        basis_ref=fixture.approval.basis_ref,
        topic_identity_slugs=fixture.topic_identity_slugs,
    )

    assert version.version_label == fixture.manifest.version_label
    assert version.creator_owner_id == approver_owner_id

    counts = _row_counts(engine)
    assert counts["canonical_graph_versions"] == 1
    assert counts["topic_identities"] == len(fixture.manifest.topics)
    assert counts["topics"] == len(fixture.manifest.topics)
    assert counts["topic_relations"] == len(fixture.manifest.relations)
    assert counts["content_revisions"] == len(fixture.manifest.content_revisions)
    assert counts["editorial_approvals"] == 1

    # Readable through the approval-gated reads immediately.
    with uow_factory() as uow:
        read_back = uow.canonical.get_published_version(version.id)
        topics = uow.canonical.get_published_topics(version.id)
    assert read_back is not None
    assert read_back.id == version.id
    assert {topic.stable_id for topic in topics} == {t.stable_id for t in fixture.manifest.topics}

    # One audit event, attributed to the editorial role, not learner.
    with engine.connect() as connection:
        actor_role, action = connection.execute(
            text(
                "SELECT actor_role, action FROM audit_events WHERE entity_id = :version_id"
            ),
            {"version_id": version.id},
        ).one()
    assert actor_role == Role.DESIGNATED_EDITORIAL_APPROVER.value
    assert action == "canonical_graph_version_published"


def test_publish_reuses_existing_topic_identity_across_versions(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    """v2_approved carries some of v1's stable ids forward; publishing both
    must not create a second `topic_identities` row for a stable id that
    already has one (spec §4.3: identities persist across versions).
    """
    v1 = load_fixture("v1_approved")
    v2 = load_fixture("v2_approved")
    assert v1.approval is not None
    assert v2.approval is not None

    publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=v1.manifest,
        actor_owner_id=approver_owner_id,
        basis_ref=v1.approval.basis_ref,
        topic_identity_slugs=v1.topic_identity_slugs,
    )
    publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=v2.manifest,
        actor_owner_id=approver_owner_id,
        basis_ref=v2.approval.basis_ref,
        topic_identity_slugs=v2.topic_identity_slugs,
    )

    v1_ids = {t.stable_id for t in v1.manifest.topics}
    v2_ids = {t.stable_id for t in v2.manifest.topics}
    expected_identity_count = len(v1_ids | v2_ids)

    with engine.connect() as connection:
        identity_count = connection.execute(
            select(func.count()).select_from(TopicIdentityRow)
        ).scalar_one()
    assert identity_count == expected_identity_count


# ---------------------------------------------------------------------------
# Validation failure: rejected before any write.
# ---------------------------------------------------------------------------


def test_validation_failure_rejected_before_any_write(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    fixture = load_fixture("invalid_prerequisite_cycle")

    with pytest.raises(DomainValidationError) as exc_info:
        publish_canonical_graph(
            engine=engine,
            uow_factory=uow_factory,
            manifest=fixture.manifest,
            actor_owner_id=approver_owner_id,
            basis_ref="fixture-basis-should-never-be-used",
            topic_identity_slugs=fixture.topic_identity_slugs,
        )

    assert exc_info.value.field_errors
    assert any(
        field_error["code"] == "prerequisite_cycle" for field_error in exc_info.value.field_errors
    )
    _assert_canonical_tables_empty(engine)


# ---------------------------------------------------------------------------
# Missing editorial grant: rejected before any write.
# ---------------------------------------------------------------------------


def test_learner_only_grant_rejected_before_any_write(
    engine: Engine, uow_factory: UnitOfWorkFactory, learner_only_owner_id: str
) -> None:
    fixture = load_fixture("v1_approved")
    assert fixture.approval is not None

    with pytest.raises(RoleNotGrantedError):
        publish_canonical_graph(
            engine=engine,
            uow_factory=uow_factory,
            manifest=fixture.manifest,
            actor_owner_id=learner_only_owner_id,
            basis_ref=fixture.approval.basis_ref,
            topic_identity_slugs=fixture.topic_identity_slugs,
        )

    _assert_canonical_tables_empty(engine)


# ---------------------------------------------------------------------------
# basis_ref validation (IDK-002 §4/§8): each of the four named failure modes
# is rejected before any write. `validate_basis_ref` itself is unit-tested
# exhaustively in `tests/unit/test_canonical_basis_ref_validation.py`; these
# four prove the *wiring* -- that `publish_canonical_graph` actually calls
# it, in the right place, for one representative case of each failure mode.
# ---------------------------------------------------------------------------


def test_basis_ref_invalid_json_rejected_before_any_write(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    fixture = load_fixture("v1_approved")

    with pytest.raises(DomainValidationError) as exc_info:
        publish_canonical_graph(
            engine=engine,
            uow_factory=uow_factory,
            manifest=fixture.manifest,
            actor_owner_id=approver_owner_id,
            basis_ref="not valid json {",
            topic_identity_slugs=fixture.topic_identity_slugs,
        )

    assert exc_info.value.field_errors
    assert any(
        field_error["code"] == "basis_ref_not_valid_json"
        for field_error in exc_info.value.field_errors
    )
    _assert_canonical_tables_empty(engine)


def test_basis_ref_missing_required_field_rejected_before_any_write(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    fixture = load_fixture("v1_approved")
    assert fixture.approval is not None
    payload = json.loads(fixture.approval.basis_ref)
    del payload["approver_is_sole_content_author"]

    with pytest.raises(DomainValidationError) as exc_info:
        publish_canonical_graph(
            engine=engine,
            uow_factory=uow_factory,
            manifest=fixture.manifest,
            actor_owner_id=approver_owner_id,
            basis_ref=json.dumps(payload),
            topic_identity_slugs=fixture.topic_identity_slugs,
        )

    assert exc_info.value.field_errors
    assert any(
        field_error["code"] == "basis_ref_missing_field"
        for field_error in exc_info.value.field_errors
    )
    _assert_canonical_tables_empty(engine)


def test_basis_ref_reviewed_manifest_hash_mismatch_rejected_before_any_write(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    fixture = load_fixture("v1_approved")
    assert fixture.approval is not None
    payload = json.loads(fixture.approval.basis_ref)
    # A well-formed but wrong hash -- not the fixture's own recomputed
    # manifest hash, so the cross-check against `manifest.manifest_hash`
    # (validated, not file-trusted -- see publisher.py) must fire.
    payload["reviewed_manifest_hash"] = "0" * 64

    with pytest.raises(DomainValidationError) as exc_info:
        publish_canonical_graph(
            engine=engine,
            uow_factory=uow_factory,
            manifest=fixture.manifest,
            actor_owner_id=approver_owner_id,
            basis_ref=json.dumps(payload),
            topic_identity_slugs=fixture.topic_identity_slugs,
        )

    assert exc_info.value.field_errors
    assert any(
        field_error["code"] == "basis_ref_manifest_hash_mismatch"
        for field_error in exc_info.value.field_errors
    )
    _assert_canonical_tables_empty(engine)


def test_basis_ref_review_kind_published_state_mismatch_rejected_before_any_write(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    """`review_kind` depends on DB state at publish time (IDK-002 §4): once
    a version is already published, a second publish's basis_ref must say
    `"diff"`, not `"initial"`. Publishes a good v1 first (so there is a
    prior published version), then attempts v2 with its `review_kind`
    forced back to `"initial"` -- rejected, and the second attempt leaves
    no partial rows behind (v1's own rows, from the first successful
    publish, are the only ones present before and after).
    """
    v1 = load_fixture("v1_approved")
    v2 = load_fixture("v2_approved")
    assert v1.approval is not None
    assert v2.approval is not None

    publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=v1.manifest,
        actor_owner_id=approver_owner_id,
        basis_ref=v1.approval.basis_ref,
        topic_identity_slugs=v1.topic_identity_slugs,
    )
    counts_after_v1 = _row_counts(engine)

    payload = json.loads(v2.approval.basis_ref)
    payload["review_kind"] = "initial"
    payload["diff_against_version_label"] = None
    payload["diff_review"] = None

    with pytest.raises(DomainValidationError) as exc_info:
        publish_canonical_graph(
            engine=engine,
            uow_factory=uow_factory,
            manifest=v2.manifest,
            actor_owner_id=approver_owner_id,
            basis_ref=json.dumps(payload),
            topic_identity_slugs=v2.topic_identity_slugs,
        )

    assert exc_info.value.field_errors
    assert any(
        field_error["code"] == "basis_ref_review_kind_published_state_mismatch"
        for field_error in exc_info.value.field_errors
    )
    # Nothing from the rejected v2 attempt was added on top of v1's rows.
    assert _row_counts(engine) == counts_after_v1


# ---------------------------------------------------------------------------
# A real mid-transaction constraint violation rolls back everything already
# flushed earlier in the same transaction, not just the failing insert.
# ---------------------------------------------------------------------------


def _manifest_with_duplicate_content_revision_hash() -> CanonicalGraphManifest:
    """A manifest `validate_manifest` accepts cleanly (it does not check
    content-revision duplicates -- see `validation.py`) but whose two
    content revisions collide on `uq_content_revision_hash`
    (`graph_version_id`, `topic_stable_id`, `layer`, `markdown_hash`),
    raising a real `IntegrityError` at the database layer.
    """
    topic = Topic(
        graph_version_id="",
        stable_id="fixture-topic-mid-txn-failure",
        title="[SYNTHETIC] Fixture Topic Mid-Transaction Failure",
        subject="java",
        scope_tags=("fixture-tag",),
        level_tag="fixture-level-1",
        target_capability="understand",
        recommended_layer="Essential",
        checkpoint_start=0,
        checkpoint_end=1,
    )
    revision_kwargs = {
        "graph_version_id": "",
        "topic_stable_id": topic.stable_id,
        "layer": "Essential",
        "kind": "fixture-kind-explanation",
        "status": "published",
        "markdown_ref": "fixture://canonical/mid-txn-failure/essential.md",
        "markdown_hash": "fixture-markdown-hash-duplicate",
        "prompt_template_version": None,
        "creator_owner_id": "",
        "supersedes_revision_id": None,
        "created_at": "",
    }
    first_revision = ContentRevision(id="fixture-content-mid-txn-1", **revision_kwargs)
    second_revision = ContentRevision(id="fixture-content-mid-txn-2", **revision_kwargs)

    manifest_without_hash = CanonicalGraphManifest(
        version_label="fixture-canonical-mid-txn-failure",
        manifest_version="1",
        manifest_hash="",
        topics=(topic,),
        relations=(),
        content_revisions=(first_revision, second_revision),
    )
    return replace(
        manifest_without_hash, manifest_hash=compute_manifest_hash(manifest_without_hash)
    )


def test_mid_transaction_constraint_violation_rolls_back_everything(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    manifest = _manifest_with_duplicate_content_revision_hash()

    with pytest.raises(IntegrityError):
        publish_canonical_graph(
            engine=engine,
            uow_factory=uow_factory,
            manifest=manifest,
            actor_owner_id=approver_owner_id,
            basis_ref=_basis_ref_payload(manifest_hash=manifest.manifest_hash),
            topic_identity_slugs={manifest.topics[0].stable_id: manifest.topics[0].stable_id},
        )

    # Not just the second (failing) content revision -- the version, the
    # topic identity and topic, and the first content revision, all
    # flushed successfully earlier in the same transaction, must also be
    # gone: nothing partial is ever readable.
    _assert_canonical_tables_empty(engine)


# ---------------------------------------------------------------------------
# Step 7: no re-publish under a reused label/hash; the version this test
# itself publishes is immutable end-to-end through the real publish path.
# ---------------------------------------------------------------------------


def test_republish_under_same_version_label_rejected(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    fixture = load_fixture("v1_approved")
    assert fixture.approval is not None

    publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=fixture.manifest,
        actor_owner_id=approver_owner_id,
        basis_ref=fixture.approval.basis_ref,
        topic_identity_slugs=fixture.topic_identity_slugs,
    )
    counts_after_first_publish = _row_counts(engine)

    with pytest.raises(ConflictError):
        publish_canonical_graph(
            engine=engine,
            uow_factory=uow_factory,
            manifest=fixture.manifest,
            actor_owner_id=approver_owner_id,
            # A prior version -- this same fixture -- now exists, so a
            # basis_ref honestly describing publish state must say "diff"
            # against the label just published, not reuse the "initial"
            # basis_ref from the first call above (that would now fail
            # basis_ref validation itself, masking the conflict rejection
            # this test actually targets).
            basis_ref=_basis_ref_payload(
                manifest_hash=fixture.manifest.manifest_hash,
                review_kind="diff",
                diff_against_version_label=fixture.manifest.version_label,
            ),
            topic_identity_slugs=fixture.topic_identity_slugs,
        )

    # Nothing was added or changed by the rejected re-publish attempt.
    assert _row_counts(engine) == counts_after_first_publish


def test_published_version_from_real_publish_rejects_direct_mutation(
    engine: Engine, uow_factory: UnitOfWorkFactory, approver_owner_id: str
) -> None:
    fixture = load_fixture("v1_approved")
    assert fixture.approval is not None

    version = publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=fixture.manifest,
        actor_owner_id=approver_owner_id,
        basis_ref=fixture.approval.basis_ref,
        topic_identity_slugs=fixture.topic_identity_slugs,
    )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE canonical_graph_versions SET version_label = 'tampered' WHERE id = :id"),
            {"id": version.id},
        )

    with engine.connect() as connection:
        label = connection.execute(
            text("SELECT version_label FROM canonical_graph_versions WHERE id = :id"),
            {"id": version.id},
        ).scalar_one()
    assert label == fixture.manifest.version_label

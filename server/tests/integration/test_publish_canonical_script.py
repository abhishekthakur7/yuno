"""Integration tests for the offline publisher *script*
(`scripts/publish_canonical.py`), covering IDK-002 §8 item 3: `load_manifest`
must construct and validate the section 4 `basis_ref` object from the
manifest's `approval` block, rejecting a mismatched shape via the script's
existing exit-code-2 convention, not forwarding it as an opaque string.

Drives `main`/`load_manifest` directly (via `importlib`, since `scripts/`
carries no `__init__.py` and isn't on `pythonpath`) against a scratch,
migrated SQLite database built fresh per test by `tests/conftest.py`'s
`engine`/`uow_factory`/`migrated_database_url` fixtures -- never
`server/yuno.db` or `server/.e2e.db`. Every manifest is built in `tmp_path`
here, independent of `tests/fixtures/canonical/`, which another task is
rewriting concurrently.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, func, select, text

from yuno.modules.canonical.domain import CanonicalGraphManifest, Topic
from yuno.modules.canonical.models import (
    CanonicalGraphVersionRow,
    ContentRevisionRow,
    EditorialApprovalRow,
    TopicIdentityRow,
    TopicRelationRow,
    TopicRow,
)
from yuno.modules.canonical.validation import compute_manifest_hash
from yuno.modules.identity.domain import Role
from yuno.shared.application.unit_of_work import UnitOfWorkFactory

# ---------------------------------------------------------------------------
# Load the script module directly from its file path: `server/scripts/` has
# no `__init__.py` and pyproject's `pythonpath = ["src"]` doesn't cover it,
# so a plain `import scripts.publish_canonical` isn't available here.
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "publish_canonical.py"
_spec = importlib.util.spec_from_file_location("publish_canonical_script", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
publish_canonical_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publish_canonical_script)

_CANONICAL_TABLES = (
    CanonicalGraphVersionRow,
    TopicIdentityRow,
    TopicRow,
    TopicRelationRow,
    ContentRevisionRow,
    EditorialApprovalRow,
)


def _assert_canonical_tables_empty(engine: Engine) -> None:
    with engine.connect() as connection:
        counts = {
            model.__tablename__: connection.execute(
                select(func.count()).select_from(model)
            ).scalar_one()
            for model in _CANONICAL_TABLES
        }
    assert all(count == 0 for count in counts.values()), counts


# ---------------------------------------------------------------------------
# Manifest / basis_ref builders. `manifest_hash` is always computed through
# the repo's own `compute_manifest_hash`, via the script's own
# `_topic_from_json`, never hand-written.
# ---------------------------------------------------------------------------


def _topic_payload(stable_id: str = "topic-alpha") -> dict[str, Any]:
    return {
        "stable_id": stable_id,
        "stable_slug": stable_id,
        "title": f"[SYNTHETIC] {stable_id}",
        "subject": "java",
        "scope_tags": ["core"],
        "level_tag": "level-1",
        "target_capability": "understand",
        "recommended_layer": "Essential",
        "checkpoint_start": 0,
        "checkpoint_end": 1,
    }


def _raw_manifest(version_label: str) -> dict[str, Any]:
    return {
        "version_label": version_label,
        "manifest_version": "1",
        "topics": [_topic_payload()],
        "relations": [],
        "content_revisions": [],
    }


def _expected_manifest_hash(raw: dict[str, Any]) -> str:
    """The hash `load_manifest` will itself recompute for `raw` -- built by
    mapping `raw["topics"]` into `Topic` the same way `load_manifest`'s own
    (private) `_topic_from_json` does, then calling the repo's
    `compute_manifest_hash`, never hand-writing a hash.
    """
    topics = tuple(
        Topic(
            graph_version_id="",
            stable_id=t["stable_id"],
            title=t["title"],
            subject=t["subject"],
            scope_tags=tuple(t["scope_tags"]),
            level_tag=t["level_tag"],
            target_capability=t["target_capability"],
            recommended_layer=t["recommended_layer"],
            checkpoint_start=t["checkpoint_start"],
            checkpoint_end=t["checkpoint_end"],
        )
        for t in raw["topics"]
    )
    manifest_without_hash = CanonicalGraphManifest(
        version_label=raw["version_label"],
        manifest_version=raw["manifest_version"],
        manifest_hash="",
        topics=topics,
        relations=(),
        content_revisions=(),
    )
    return compute_manifest_hash(manifest_without_hash)


def _valid_basis_ref_obj(manifest_hash: str) -> dict[str, Any]:
    """A fully valid IDK-002 §4 `basis_ref` object reviewing `manifest_hash`
    as an `"initial"` review (no prior published version in a fresh
    scratch database, which every test here uses)."""
    return {
        "basis_ref_version": "editorial-approval-basis-v1",
        "policy_identifier": "editorial-approval-criteria-v1",
        "reviewed_manifest_hash": manifest_hash,
        "checklist_completed_at": "2026-08-15T00:00:00Z",
        "review_kind": "initial",
        "diff_against_version_label": None,
        "curriculum_boundary_review": {
            "result": "pass",
            "topics_reviewed": 1,
            "topics_total": 1,
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
            "structural_claims_reviewed": 0,
            "structural_claims_total": 0,
            "live_check_sample_size": 0,
            "live_check_population_size": 0,
            "live_check_result": "pass",
        },
        "layer_reversal_review": {
            "result": "pass",
            "topics_reviewed": 1,
            "topics_total": 1,
        },
        "half_seed_immutability_check": {"result": "pass"},
        "diff_review": None,
        "approver_is_sole_content_author": True,
    }


def _write_manifest(tmp_path: Path, *, version_label: str, basis_ref_text: str) -> Path:
    raw = _raw_manifest(version_label)
    raw["approval"] = {
        "approver_role": "designated_editorial_approver",
        "basis_ref": basis_ref_text,
    }
    manifest_path = tmp_path / f"{version_label}.json"
    manifest_path.write_text(json.dumps(raw))
    return manifest_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def approver_owner_id(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Fixture Script Approver")
        uow.owners.grant_role(
            owner.id, Role.DESIGNATED_EDITORIAL_APPROVER, assigned_by_owner_id=owner.id
        )
        uow.commit()
    return owner.id


# ---------------------------------------------------------------------------
# Exit-code-2 shape rejections.
# ---------------------------------------------------------------------------


def test_basis_ref_not_valid_json_exits_2(
    tmp_path: Path, engine: Engine, migrated_database_url: str, approver_owner_id: str
) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        version_label="v-not-json",
        basis_ref_text="{this is not valid json",
    )

    exit_code = publish_canonical_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            approver_owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2
    _assert_canonical_tables_empty(engine)


def test_basis_ref_valid_json_but_not_object_exits_2(
    tmp_path: Path, engine: Engine, migrated_database_url: str, approver_owner_id: str
) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        version_label="v-not-object",
        basis_ref_text=json.dumps([1, 2, 3]),
    )

    exit_code = publish_canonical_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            approver_owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2
    _assert_canonical_tables_empty(engine)


def test_basis_ref_missing_required_field_exits_2(
    tmp_path: Path, engine: Engine, migrated_database_url: str, approver_owner_id: str
) -> None:
    raw = _raw_manifest("v-missing-field")
    manifest_hash = _expected_manifest_hash(raw)
    basis_ref_obj = _valid_basis_ref_obj(manifest_hash)
    del basis_ref_obj["checklist_completed_at"]

    manifest_path = _write_manifest(
        tmp_path,
        version_label="v-missing-field",
        basis_ref_text=json.dumps(basis_ref_obj),
    )

    exit_code = publish_canonical_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            approver_owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2
    _assert_canonical_tables_empty(engine)


def test_basis_ref_reviewed_manifest_hash_mismatch_exits_2(
    tmp_path: Path, engine: Engine, migrated_database_url: str, approver_owner_id: str
) -> None:
    raw = _raw_manifest("v-hash-mismatch")
    manifest_hash = _expected_manifest_hash(raw)
    basis_ref_obj = _valid_basis_ref_obj(manifest_hash)
    basis_ref_obj["reviewed_manifest_hash"] = "0" * 64  # does not match

    manifest_path = _write_manifest(
        tmp_path,
        version_label="v-hash-mismatch",
        basis_ref_text=json.dumps(basis_ref_obj),
    )

    exit_code = publish_canonical_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            approver_owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2
    _assert_canonical_tables_empty(engine)


def test_basis_ref_unknown_extra_field_exits_2(
    tmp_path: Path, engine: Engine, migrated_database_url: str, approver_owner_id: str
) -> None:
    raw = _raw_manifest("v-unknown-field")
    manifest_hash = _expected_manifest_hash(raw)
    basis_ref_obj = _valid_basis_ref_obj(manifest_hash)
    basis_ref_obj["totally_unexpected_field"] = "surprise"

    manifest_path = _write_manifest(
        tmp_path,
        version_label="v-unknown-field",
        basis_ref_text=json.dumps(basis_ref_obj),
    )

    exit_code = publish_canonical_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            approver_owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2
    _assert_canonical_tables_empty(engine)


# ---------------------------------------------------------------------------
# Happy path: a fully valid basis_ref publishes for real.
# ---------------------------------------------------------------------------


def test_well_formed_basis_ref_exits_0_and_publishes(
    tmp_path: Path, engine: Engine, migrated_database_url: str, approver_owner_id: str
) -> None:
    raw = _raw_manifest("v-valid")
    manifest_hash = _expected_manifest_hash(raw)
    basis_ref_obj = _valid_basis_ref_obj(manifest_hash)
    basis_ref_text = json.dumps(basis_ref_obj)

    manifest_path = _write_manifest(
        tmp_path, version_label="v-valid", basis_ref_text=basis_ref_text
    )

    exit_code = publish_canonical_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            approver_owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 0

    with engine.connect() as connection:
        version_id, stored_basis_ref = connection.execute(
            text(
                "SELECT ea.graph_version_id, ea.basis_ref "
                "FROM editorial_approvals ea "
                "JOIN canonical_graph_versions v ON v.id = ea.graph_version_id "
                "WHERE v.version_label = :version_label"
            ),
            {"version_label": "v-valid"},
        ).one()

    assert version_id
    assert json.loads(stored_basis_ref) == basis_ref_obj


def test_load_manifest_returns_validated_basis_ref_text(tmp_path: Path) -> None:
    """`load_manifest` itself (not just `main`) returns the same
    JSON-text `basis_ref` string it validated, unchanged."""
    raw = _raw_manifest("v-load-manifest")
    manifest_hash = _expected_manifest_hash(raw)
    basis_ref_obj = _valid_basis_ref_obj(manifest_hash)
    basis_ref_text = json.dumps(basis_ref_obj)

    manifest_path = _write_manifest(
        tmp_path, version_label="v-load-manifest", basis_ref_text=basis_ref_text
    )

    manifest, topic_identity_slugs, approver_role, basis_ref = (
        publish_canonical_script.load_manifest(manifest_path)
    )

    assert manifest.manifest_hash == manifest_hash
    assert topic_identity_slugs == {"topic-alpha": "topic-alpha"}
    assert approver_role == "designated_editorial_approver"
    assert basis_ref == basis_ref_text
    assert json.loads(basis_ref) == basis_ref_obj

"""Integration coverage for the offline rubric-manifest loader CLI
(`scripts/load_rubric_manifest.py`), covering IDK-503 gate 5 blocking
finding B11's mechanism half: `rubrics`/`rubric_dimensions` had zero rows
and no production caller of `uow.evidence.add_rubric` outside tests and
`scripts/seed_performance_dataset.py`'s synthetic fixture. This script is
that production entry point, and this file proves a rubric header and its
six dimensions are genuinely persisted *through it* -- a real `main([...])`
call, not a call to `load_rubric_manifest` directly.

Every manifest used here is written into `tmp_path` and is obviously
synthetic (`Synthetic ... (TEST FIXTURE)` text, `synthetic-test-*` stable
dimension ids) -- IDK-204's own text permits mechanism tests to use
synthetic mappings, and this file authors no IDK-009 rubric content.

Drives `main` directly (via `importlib`, since `scripts/` carries no
`__init__.py` and isn't on `pythonpath` -- same trick
`test_withdraw_source_script.py`/`test_publish_canonical_script.py` use)
against a scratch, migrated SQLite database built fresh per test by
`tests/conftest.py`'s `engine`/`uow_factory`/`migrated_database_url`
fixtures -- never `server/yuno.db` or `server/.e2e.db`.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text

from yuno.modules.evidence_evaluation.domain import RubricStatus
from yuno.modules.identity.domain import Role
from yuno.shared.application.unit_of_work import UnitOfWorkFactory

# ---------------------------------------------------------------------------
# Load the script module directly from its file path: `server/scripts/` has
# no `__init__.py` and pyproject's `pythonpath = ["src"]` doesn't cover it,
# so a plain `import scripts.load_rubric_manifest` isn't available here
# (same constraint the sibling script test files document).
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "load_rubric_manifest.py"
)
_spec = importlib.util.spec_from_file_location(
    "load_rubric_manifest_script", _SCRIPT_PATH
)
assert _spec is not None and _spec.loader is not None
load_rubric_manifest_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_rubric_manifest_script)


# ---------------------------------------------------------------------------
# Synthetic manifest fixtures. All text is deliberately marked as a test
# fixture; the two critical stable dimension ids are IDK-009 §6's own ids
# (`CRITICAL_STABLE_DIMENSION_IDS`, `domain.py:607-609`) since the loader's
# critical-dimension check keys on those exact strings -- the other four are
# obviously synthetic placeholders, never IDK-009 §6's real names.
# ---------------------------------------------------------------------------


def _base_dimensions() -> list[dict[str, Any]]:
    return [
        {
            "stable_dimension_id": "factual-and-mechanical-correctness",
            "name": "Synthetic Dimension One (TEST FIXTURE)",
            "description": "Synthetic test-only dimension description.",
            "ordinal": 1,
            "evaluation_guidance": "Synthetic test-only evaluation guidance.",
        },
        {
            "stable_dimension_id": "assumptions-and-constraints",
            "name": "Synthetic Dimension Two (TEST FIXTURE)",
            "description": "Synthetic test-only dimension description.",
            "ordinal": 2,
            "evaluation_guidance": "Synthetic test-only evaluation guidance.",
        },
        {
            "stable_dimension_id": "synthetic-test-dimension-three",
            "name": "Synthetic Dimension Three (TEST FIXTURE)",
            "description": "Synthetic test-only dimension description.",
            "ordinal": 3,
            "evaluation_guidance": "Synthetic test-only evaluation guidance.",
        },
        {
            "stable_dimension_id": "synthetic-test-dimension-four",
            "name": "Synthetic Dimension Four (TEST FIXTURE)",
            "description": "Synthetic test-only dimension description.",
            "ordinal": 4,
            "evaluation_guidance": "Synthetic test-only evaluation guidance.",
        },
        {
            "stable_dimension_id": "synthetic-test-dimension-five",
            "name": "Synthetic Dimension Five (TEST FIXTURE)",
            "description": "Synthetic test-only dimension description.",
            "ordinal": 5,
            "evaluation_guidance": "Synthetic test-only evaluation guidance.",
        },
        {
            "stable_dimension_id": "synthetic-test-dimension-six",
            "name": "Synthetic Dimension Six (TEST FIXTURE)",
            "description": "Synthetic test-only dimension description.",
            "ordinal": 6,
            "evaluation_guidance": "Synthetic test-only evaluation guidance.",
        },
    ]


def _manifest_dict(
    *,
    capability: str = "implement",
    version: str = "synthetic-test-v1",
    status: str = "approved",
    task_context: str = "Synthetic test-only task context (TEST FIXTURE).",
    provenance: str = "Synthetic test-only provenance (TEST FIXTURE).",
    dimensions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "capability": capability,
        "version": version,
        "role": None,
        "level": None,
        "status": status,
        "task_context": task_context,
        "provenance": provenance,
        "dimensions": dimensions if dimensions is not None else _base_dimensions(),
    }


def _write_manifest(tmp_path: Path, payload: dict[str, Any], *, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload))
    return path


def _approver_owner_id(uow_factory: UnitOfWorkFactory) -> str:
    """A local owner holding `designated_editorial_approver` -- the grant
    `load_rubric_manifest` requires before any write, mirroring
    `test_withdraw_source_script.py`'s identical fixture idiom.
    """
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Script Approver")
        uow.owners.grant_role(
            owner.id, Role.DESIGNATED_EDITORIAL_APPROVER, assigned_by_owner_id=owner.id
        )
        uow.commit()
    return owner.id


def _learner_only_owner_id(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Script Learner")
        uow.owners.grant_role(owner.id, Role.LEARNER, assigned_by_owner_id=owner.id)
        uow.commit()
    return owner.id


def _rubric_count(engine: Engine, owner_id: str) -> int:
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT count(*) FROM rubrics WHERE owner_id=:owner_id"),
            {"owner_id": owner_id},
        )


def _run(manifest_path: Path, owner_id: str, database_url: str) -> int:
    return load_rubric_manifest_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            owner_id,
            "--database-url",
            database_url,
        ]
    )


# ---------------------------------------------------------------------------
# Happy path: the rubric header and its six dimensions genuinely persist
# through `main`.
# ---------------------------------------------------------------------------


def test_load_persists_header_and_six_dimensions_through_main(
    uow_factory: UnitOfWorkFactory, migrated_database_url: str, tmp_path: Path
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    manifest_path = _write_manifest(tmp_path, _manifest_dict(), name="manifest.json")

    exit_code = _run(manifest_path, owner_id, migrated_database_url)

    assert exit_code == 0
    with uow_factory() as uow:
        rubrics = uow.evidence.list_rubrics(owner_id)
        assert len(rubrics) == 1
        rubric = rubrics[0]
        assert rubric.status is RubricStatus.APPROVED
        assert rubric.capability == "implement"
        assert rubric.version == "synthetic-test-v1"
        dimensions = uow.evidence.list_rubric_dimensions(owner_id, rubric.id)
    assert len(dimensions) == 6
    assert sorted(dimension.ordinal for dimension in dimensions) == [1, 2, 3, 4, 5, 6]
    assert {dimension.stable_dimension_id for dimension in dimensions} == {
        "factual-and-mechanical-correctness",
        "assumptions-and-constraints",
        "synthetic-test-dimension-three",
        "synthetic-test-dimension-four",
        "synthetic-test-dimension-five",
        "synthetic-test-dimension-six",
    }


# ---------------------------------------------------------------------------
# Exit 1: a `YunoError` anywhere before or during loading, always writing
# nothing.
# ---------------------------------------------------------------------------


def test_load_refused_when_actor_lacks_the_grant_exits_1_and_writes_nothing(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner_id = _learner_only_owner_id(uow_factory)
    manifest_path = _write_manifest(tmp_path, _manifest_dict(), name="manifest.json")

    exit_code = _run(manifest_path, owner_id, migrated_database_url)

    assert exit_code == 1
    stderr = capsys.readouterr().err
    assert "[role_not_granted]" in stderr
    assert _rubric_count(engine, owner_id) == 0


def test_reloading_same_capability_version_with_different_body_exits_1_and_leaves_original_untouched(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    first_manifest = _write_manifest(
        tmp_path,
        _manifest_dict(task_context="Synthetic original task context (TEST FIXTURE)."),
        name="first.json",
    )
    assert _run(first_manifest, owner_id, migrated_database_url) == 0
    assert _rubric_count(engine, owner_id) == 1

    # Same (capability, version) but a genuinely different body -- the DB's
    # own UniqueConstraint("owner_id","body_hash","capability","version")
    # would *not* catch this on its own (different body_hash); the version
    # gate lives in `load_rubric_manifest` itself.
    second_manifest = _write_manifest(
        tmp_path,
        _manifest_dict(task_context="Synthetic REDEFINED task context (TEST FIXTURE)."),
        name="second.json",
    )

    exit_code = _run(second_manifest, owner_id, migrated_database_url)

    assert exit_code == 1
    assert _rubric_count(engine, owner_id) == 1
    with uow_factory() as uow:
        rubrics = uow.evidence.list_rubrics(owner_id)
        assert len(rubrics) == 1
        assert (
            rubrics[0].task_context == "Synthetic original task context (TEST FIXTURE)."
        )


def test_manifest_with_five_dimensions_exits_1(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    manifest_path = _write_manifest(
        tmp_path,
        _manifest_dict(dimensions=_base_dimensions()[:5]),
        name="manifest.json",
    )

    exit_code = _run(manifest_path, owner_id, migrated_database_url)

    assert exit_code == 1
    assert _rubric_count(engine, owner_id) == 0


def test_manifest_with_duplicate_ordinal_exits_1(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    dimensions = _base_dimensions()
    dimensions[1]["ordinal"] = 1  # duplicate of dimensions[0]'s ordinal
    manifest_path = _write_manifest(
        tmp_path, _manifest_dict(dimensions=dimensions), name="manifest.json"
    )

    exit_code = _run(manifest_path, owner_id, migrated_database_url)

    assert exit_code == 1
    assert _rubric_count(engine, owner_id) == 0


def test_manifest_missing_a_critical_stable_dimension_exits_1(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    dimensions = _base_dimensions()
    # Replace the "assumptions-and-constraints" critical dimension with
    # another synthetic, non-critical one -- six dimensions, six distinct
    # ordinals and stable ids, but only one critical dimension present.
    dimensions[1]["stable_dimension_id"] = "synthetic-test-dimension-seven"
    manifest_path = _write_manifest(
        tmp_path, _manifest_dict(dimensions=dimensions), name="manifest.json"
    )

    exit_code = _run(manifest_path, owner_id, migrated_database_url)

    assert exit_code == 1
    assert _rubric_count(engine, owner_id) == 0


def test_manifest_with_non_approved_status_exits_1(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    manifest_path = _write_manifest(
        tmp_path, _manifest_dict(status="fixture"), name="manifest.json"
    )

    exit_code = _run(manifest_path, owner_id, migrated_database_url)

    assert exit_code == 1
    assert _rubric_count(engine, owner_id) == 0


def test_unmigrated_database_exits_1_via_require_single_head(
    database_url: str, tmp_path: Path
) -> None:
    """`require_single_head(engine)` is checked in the CLI itself (module
    docstring), before any session is opened -- proven the same way
    `test_withdraw_source_script.py`'s equivalent test does, by pointing
    `--database-url` at the deliberately unmigrated scratch database
    `tests/conftest.py`'s `database_url` fixture builds.
    """
    manifest_path = _write_manifest(tmp_path, _manifest_dict(), name="manifest.json")

    exit_code = _run(manifest_path, "irrelevant-owner-id", database_url)

    assert exit_code == 1


# ---------------------------------------------------------------------------
# Exit 2: a usage/manifest error.
# ---------------------------------------------------------------------------


def test_missing_manifest_file_exits_2(
    migrated_database_url: str, tmp_path: Path
) -> None:
    exit_code = _run(
        tmp_path / "does-not-exist.json", "irrelevant-owner-id", migrated_database_url
    )

    assert exit_code == 2


def test_malformed_manifest_json_exits_2(
    migrated_database_url: str, tmp_path: Path
) -> None:
    manifest_path = tmp_path / "malformed.json"
    manifest_path.write_text("{not valid json")

    exit_code = _run(manifest_path, "irrelevant-owner-id", migrated_database_url)

    assert exit_code == 2


def test_manifest_missing_a_required_field_exits_2(
    migrated_database_url: str, tmp_path: Path
) -> None:
    payload = _manifest_dict()
    del payload["provenance"]
    manifest_path = _write_manifest(tmp_path, payload, name="manifest.json")

    exit_code = _run(manifest_path, "irrelevant-owner-id", migrated_database_url)

    assert exit_code == 2

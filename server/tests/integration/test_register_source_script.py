"""Integration coverage for the offline editorial CLI
(`scripts/register_source.py`), covering IDK-503 gate 3 blocking finding 1
/ B4's mechanism half: `add_source` (`provenance/repository.py:44`) had no
production caller -- only tests and the fixture-shaped
`scripts/seed_performance_dataset.py:447` perf-dataset seed called it. This
script is that production entry point, and this file proves rows are
genuinely created *through it* -- real `main([...])` calls, not direct
`register_source` calls.

Drives `main` directly (via `importlib`, since `scripts/` carries no
`__init__.py` and isn't on `pythonpath` -- same trick
`test_withdraw_source_script.py`/`test_publish_canonical_script.py` use)
against a scratch, migrated SQLite database built fresh per test by
`tests/conftest.py`'s `engine`/`uow_factory`/`migrated_database_url`
fixtures -- never `server/yuno.db` or `server/.e2e.db`. Every manifest file
this suite writes lives under the test's own `tmp_path`, never the repo,
per the hard rule against shipping fixture source data outside a test's
own scratch directory.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from yuno.modules.identity.domain import Role
from yuno.modules.provenance.domain import SourceAvailability
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.ids import new_id

# ---------------------------------------------------------------------------
# Load the script module directly from its file path: `server/scripts/` has
# no `__init__.py` and pyproject's `pythonpath = ["src"]` doesn't cover it,
# so a plain `import scripts.register_source` isn't available here (same
# constraint `test_withdraw_source_script.py` documents).
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "register_source.py"
_spec = importlib.util.spec_from_file_location("register_source_script", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
register_source_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(register_source_script)


def _approver_owner_id(uow_factory: UnitOfWorkFactory) -> str:
    """A local owner holding `designated_editorial_approver` -- the grant
    `register_source` requires before any write, mirroring
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


def _source_entry(
    *,
    suffix: str,
    license_status: str = "approved-open-license",
    source_id: str | None = None,
) -> dict:
    return {
        "id": source_id or new_id(),
        "origin": "fixture",
        "source_type": "documentation",
        "title": f"Source {suffix}",
        "publisher": "Fixture publisher",
        "canonical_url": f"https://example.invalid/{suffix}",
        "license_status": license_status,
    }


def _write_manifest(
    tmp_path: Path, entries: list[dict], *, filename: str = "manifest.json"
) -> Path:
    path = tmp_path / filename
    path.write_text(json.dumps({"sources": entries}))
    return path


def _source_row_count(engine: Engine, owner_id: str) -> int:
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT count(*) FROM sources WHERE owner_id=:owner_id"),
            {"owner_id": owner_id},
        )


# ---------------------------------------------------------------------------
# Happy path: rows are genuinely created through `main`.
# ---------------------------------------------------------------------------


def test_registration_creates_rows_readable_afterwards_through_main(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    open_license_entry = _source_entry(
        suffix="alpha", license_status="approved-open-license"
    )
    link_only_entry = _source_entry(suffix="beta", license_status="approved-link-only")
    manifest_path = _write_manifest(tmp_path, [open_license_entry, link_only_entry])

    exit_code = register_source_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 0
    assert _source_row_count(engine, owner_id) == 2

    with uow_factory() as uow:
        open_license_source = uow.provenance.get_source(
            owner_id, open_license_entry["id"]
        )
        link_only_source = uow.provenance.get_source(owner_id, link_only_entry["id"])

    assert open_license_source is not None
    assert open_license_source.license_status == "approved-open-license"
    assert open_license_source.availability_status is SourceAvailability.AVAILABLE
    assert open_license_source.withdrawal_reason is None
    assert open_license_source.superseded_by_source_id is None

    assert link_only_source is not None
    assert link_only_source.license_status == "approved-link-only"
    assert link_only_source.availability_status is SourceAvailability.AVAILABLE


# ---------------------------------------------------------------------------
# Exit 1: a `YunoError` anywhere before or during registration, writing
# nothing -- the fail-closed claim proven by a real row count, not asserted.
# ---------------------------------------------------------------------------


def test_actor_without_the_grant_is_refused_and_writes_nothing(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner_id = _learner_only_owner_id(uow_factory)
    manifest_path = _write_manifest(tmp_path, [_source_entry(suffix="gamma")])

    exit_code = register_source_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 1
    stderr = capsys.readouterr().err
    assert "[role_not_granted]" in stderr
    assert _source_row_count(engine, owner_id) == 0


def test_reregistering_an_existing_id_exits_1_and_does_not_duplicate(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    entry = _source_entry(suffix="delta")
    first_manifest = _write_manifest(tmp_path, [entry], filename="first.json")

    first_exit = register_source_script.main(
        [
            str(first_manifest),
            "--actor-owner-id",
            owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )
    assert first_exit == 0
    assert _source_row_count(engine, owner_id) == 1

    second_manifest = _write_manifest(tmp_path, [entry], filename="second.json")
    second_exit = register_source_script.main(
        [
            str(second_manifest),
            "--actor-owner-id",
            owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert second_exit == 1
    assert _source_row_count(engine, owner_id) == 1


def test_duplicate_id_within_one_manifest_batch_commits_nothing(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    """Proves batch atomicity end-to-end through the CLI: a manifest whose
    second entry collides with its own first entry's id must leave zero
    rows behind, not one -- `register_source` runs the whole batch inside a
    single transaction (its own docstring), so a mid-batch `ConflictError`
    rolls back everything already flushed, not just the offending entry.
    """
    owner_id = _approver_owner_id(uow_factory)
    shared_id = new_id()
    first_entry = _source_entry(suffix="epsilon-1", source_id=shared_id)
    second_entry = _source_entry(suffix="epsilon-2", source_id=shared_id)
    manifest_path = _write_manifest(tmp_path, [first_entry, second_entry])

    exit_code = register_source_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 1
    assert _source_row_count(engine, owner_id) == 0


def test_unmigrated_database_exits_1_via_require_single_head(
    database_url: str, tmp_path: Path
) -> None:
    """`require_single_head(engine)` is checked in the CLI itself (module
    docstring), before any session is opened -- proven by pointing
    `--database-url` at the deliberately unmigrated scratch database
    `tests/conftest.py`'s `database_url` fixture builds (as opposed to
    `migrated_database_url`, which every other test in this file uses),
    mirroring `test_withdraw_source_script.py`'s identical test.

    Deliberately requests only the `database_url` fixture, not
    `migrated_database_url`/`engine`/`uow_factory`: those all migrate the
    same `tmp_path` file `database_url` points to as a side effect
    (`conftest.py`) -- requesting any of them here would migrate the very
    file this test needs to stay unmigrated.
    """
    manifest_path = _write_manifest(tmp_path, [_source_entry(suffix="zeta")])

    exit_code = register_source_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            "irrelevant-owner-id",
            "--database-url",
            database_url,
        ]
    )

    assert exit_code == 1


# ---------------------------------------------------------------------------
# Exit 2: a usage error.
# ---------------------------------------------------------------------------


def test_unrecognized_license_status_exits_2(
    migrated_database_url: str, tmp_path: Path
) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        [_source_entry(suffix="eta", license_status="fixture-approved")],
    )

    exit_code = register_source_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            "irrelevant-owner-id",
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2


def test_missing_manifest_file_exits_2(
    migrated_database_url: str, tmp_path: Path
) -> None:
    missing_path = tmp_path / "does-not-exist.json"

    exit_code = register_source_script.main(
        [
            str(missing_path),
            "--actor-owner-id",
            "irrelevant-owner-id",
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2


def test_malformed_manifest_json_exits_2(
    migrated_database_url: str, tmp_path: Path
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{this is not valid json")

    exit_code = register_source_script.main(
        [
            str(path),
            "--actor-owner-id",
            "irrelevant-owner-id",
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2


def test_manifest_missing_sources_key_exits_2(
    migrated_database_url: str, tmp_path: Path
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"not_sources": []}))

    exit_code = register_source_script.main(
        [
            str(path),
            "--actor-owner-id",
            "irrelevant-owner-id",
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2


def test_manifest_with_empty_sources_array_exits_2(
    migrated_database_url: str, tmp_path: Path
) -> None:
    manifest_path = _write_manifest(tmp_path, [])

    exit_code = register_source_script.main(
        [
            str(manifest_path),
            "--actor-owner-id",
            "irrelevant-owner-id",
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2

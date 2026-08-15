"""Integration coverage for the offline editorial CLI
(`scripts/withdraw_source.py`), covering IDK-503 gate 3 blocking finding
4 / B7 remainder: `withdraw_source` (`provenance/service.py`) had zero
production callers, so the license-revocation purge it gates could never
fire outside a direct service-layer test call. This script is that
production entry point, and this file proves the purge genuinely fires
*through it* -- a real `main([...])` call, not a call to `withdraw_source`
directly.

Drives `main` directly (via `importlib`, since `scripts/` carries no
`__init__.py` and isn't on `pythonpath` -- same trick
`test_publish_canonical_script.py` uses) against a scratch, migrated
SQLite database built fresh per test by `tests/conftest.py`'s
`engine`/`uow_factory`/`migrated_database_url` fixtures -- never
`server/yuno.db` or `server/.e2e.db`.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from yuno.modules.identity.domain import Role
from yuno.modules.provenance.domain import (
    Source,
    SourceAvailability,
    SourceSnapshot,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.ids import new_id

# ---------------------------------------------------------------------------
# Load the script module directly from its file path: `server/scripts/` has
# no `__init__.py` and pyproject's `pythonpath = ["src"]` doesn't cover it,
# so a plain `import scripts.withdraw_source` isn't available here (same
# constraint `test_publish_canonical_script.py` documents).
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "withdraw_source.py"
_spec = importlib.util.spec_from_file_location("withdraw_source_script", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
withdraw_source_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(withdraw_source_script)


def _ts(seconds: int) -> str:
    return f"2026-08-15T00:00:{seconds:02d}.000000Z"


def _content_hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _approver_owner_id(uow_factory: UnitOfWorkFactory) -> str:
    """A local owner holding `designated_editorial_approver` -- the grant
    `withdraw_source` now requires before any write, mirroring
    `test_canonical_publish.py`'s `approver_owner_id` fixture idiom.
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


def _source(uow_factory: UnitOfWorkFactory, owner_id: str, *, suffix: str) -> str:
    source = Source(
        new_id(),
        owner_id,
        "fixture",
        "documentation",
        f"Source {suffix}",
        "Fixture publisher",
        f"https://example.invalid/{suffix}",
        "approved-open-license",
        SourceAvailability.AVAILABLE,
        None,
        None,
        _ts(0),
        _ts(0),
    )
    with uow_factory() as uow:
        uow.provenance.add_source(source)
        uow.commit()
    return source.id


def _snapshot_with_body(
    uow_factory: UnitOfWorkFactory, owner_id: str, source_id: str, *, suffix: str
) -> SourceSnapshot:
    """A snapshot carrying a `source_snapshot_bodies` pointer row -- what
    the purge this test proves fires through the CLI actually deletes.
    No physical file is written: `purge_license_revoked_snapshot_bodies`
    (`adapters.py`) only touches DB rows; the out-of-transaction unlink is
    `execute_pending_cleanup`'s job, already covered by
    `test_provenance_license_purge.py`.
    """
    content_hash = _content_hash(suffix)
    snapshot = SourceSnapshot(
        new_id(),
        owner_id,
        source_id,
        _ts(1),
        f"source-snapshot:{content_hash}",
        content_hash,
        "available",
        "v1",
    )
    with uow_factory() as uow:
        uow.provenance.add_source_snapshot(snapshot)
        uow.commit()
    return snapshot


def _body_count(engine: Engine, owner_id: str, source_id: str) -> int:
    with engine.connect() as connection:
        return connection.scalar(
            text(
                "SELECT count(*) FROM source_snapshot_bodies "
                "WHERE owner_id=:owner_id AND source_id=:source_id"
            ),
            {"owner_id": owner_id, "source_id": source_id},
        )


def _snapshot_metadata_row(engine: Engine, snapshot_id: str) -> dict:
    with engine.connect() as connection:
        return dict(
            connection.execute(
                text(
                    "SELECT content_hash, retrieved_at, status FROM source_snapshots "
                    "WHERE id=:id"
                ),
                {"id": snapshot_id},
            )
            .mappings()
            .one()
        )


# ---------------------------------------------------------------------------
# Happy paths: the purge (or its deliberate absence) fires through `main`.
# ---------------------------------------------------------------------------


def test_license_revoked_withdrawal_purges_body_and_retains_snapshot_metadata(
    uow_factory: UnitOfWorkFactory, engine: Engine, migrated_database_url: str
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="license-revoked")
    snapshot = _snapshot_with_body(
        uow_factory, owner_id, source_id, suffix="license-revoked"
    )
    assert _body_count(engine, owner_id, source_id) == 1

    exit_code = withdraw_source_script.main(
        [
            source_id,
            "--reason",
            "license-revoked",
            "--actor-owner-id",
            owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 0
    # The purge genuinely fired through the production entry point: the
    # body pointer row is gone...
    assert _body_count(engine, owner_id, source_id) == 0
    # ...but `source_snapshots` metadata is retained untouched.
    row = _snapshot_metadata_row(engine, snapshot.id)
    assert row["content_hash"] == snapshot.content_hash
    assert row["retrieved_at"] == snapshot.retrieved_at
    assert row["status"] == snapshot.status

    with uow_factory() as uow:
        current = uow.provenance.get_source(owner_id, source_id)
    assert current is not None
    assert current.availability_status is SourceAvailability.WITHDRAWN
    assert current.withdrawal_reason.value == "license-revoked"


def test_non_license_reason_withdrawal_leaves_body_intact(
    uow_factory: UnitOfWorkFactory, engine: Engine, migrated_database_url: str
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="publisher-retracted")
    _snapshot_with_body(uow_factory, owner_id, source_id, suffix="publisher-retracted")
    assert _body_count(engine, owner_id, source_id) == 1

    exit_code = withdraw_source_script.main(
        [
            source_id,
            "--reason",
            "publisher-retracted",
            "--actor-owner-id",
            owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 0
    # `publisher-retracted` is not a license-revocation reason: the CLI's
    # reason-gating (inherited from `withdraw_source`) leaves the body
    # pointer row intact, proving the gate applies through this path too,
    # not just the purge-triggering path.
    assert _body_count(engine, owner_id, source_id) == 1


def test_withdrawal_with_superseded_by_source_id_records_lineage(
    uow_factory: UnitOfWorkFactory, engine: Engine, migrated_database_url: str
) -> None:
    owner_id = _approver_owner_id(uow_factory)
    old_source_id = _source(uow_factory, owner_id, suffix="old")
    new_source_id = _source(uow_factory, owner_id, suffix="new")

    exit_code = withdraw_source_script.main(
        [
            old_source_id,
            "--reason",
            "factually-superseded",
            "--actor-owner-id",
            owner_id,
            "--superseded-by-source-id",
            new_source_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 0
    with uow_factory() as uow:
        old_source = uow.provenance.get_source(owner_id, old_source_id)
        new_source = uow.provenance.get_source(owner_id, new_source_id)
    assert old_source is not None
    assert old_source.availability_status is SourceAvailability.WITHDRAWN
    assert old_source.superseded_by_source_id == new_source_id
    # Lineage is old -> new only: the replacement row is untouched.
    assert new_source is not None
    assert new_source.availability_status is SourceAvailability.AVAILABLE


# ---------------------------------------------------------------------------
# Exit 1: a `YunoError` anywhere before or during withdrawal.
# ---------------------------------------------------------------------------


def test_withdrawal_refused_when_actor_lacks_the_grant_exits_1(
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    migrated_database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner_id = _learner_only_owner_id(uow_factory)
    source_id = _source(uow_factory, owner_id, suffix="unauthorized")

    exit_code = withdraw_source_script.main(
        [
            source_id,
            "--reason",
            "license-revoked",
            "--actor-owner-id",
            owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 1
    stderr = capsys.readouterr().err
    assert "[role_not_granted]" in stderr

    with uow_factory() as uow:
        current = uow.provenance.get_source(owner_id, source_id)
    assert current is not None
    assert current.availability_status is SourceAvailability.AVAILABLE
    assert current.withdrawal_reason is None


def test_withdrawal_of_a_missing_source_exits_1(
    uow_factory: UnitOfWorkFactory, migrated_database_url: str
) -> None:
    owner_id = _approver_owner_id(uow_factory)

    exit_code = withdraw_source_script.main(
        [
            "does-not-exist",
            "--reason",
            "license-revoked",
            "--actor-owner-id",
            owner_id,
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 1


def test_unmigrated_database_exits_1_via_require_single_head(
    database_url: str,
) -> None:
    """`require_single_head(engine)` is checked in the CLI itself (module
    docstring), before any session is opened -- this proves it is wired,
    not merely documented, by pointing `--database-url` at the deliberately
    unmigrated scratch database `tests/conftest.py`'s `database_url`
    fixture builds (as opposed to `migrated_database_url`, which every
    other test in this file uses).

    Deliberately requests only the `database_url` fixture, not
    `migrated_database_url`/`engine`/`uow_factory`: those all depend on
    `migrated_database_url`, which migrates the *same* `tmp_path` file
    `database_url` points to as a side effect (`conftest.py`) -- requesting
    any of them here would migrate the very file this test needs to stay
    unmigrated. No real owner/source row is needed either: the guard must
    fail before `withdraw_source` ever opens a session to look one up.
    """
    exit_code = withdraw_source_script.main(
        [
            "irrelevant-source-id",
            "--reason",
            "license-revoked",
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


def test_unrecognized_reason_value_exits_2(migrated_database_url: str) -> None:
    exit_code = withdraw_source_script.main(
        [
            "irrelevant-source-id",
            "--reason",
            "not-a-real-reason",
            "--actor-owner-id",
            "irrelevant-owner-id",
            "--database-url",
            migrated_database_url,
        ]
    )

    assert exit_code == 2

"""`basis_ref_valid` CHECK constraint on `editorial_approvals` (IDK-002
section 8 item 1; IDK-503 finding B2 part a): `CheckConstraint("json_valid(basis_ref)",
name="basis_ref_valid")`, mirroring the existing `payload_json_valid`
pattern elsewhere in the schema.

The migration that adds this constraint (`4747447ccaa3`) rebuilds
`editorial_approvals` via `op.batch_alter_table`, which -- per
`test_canonical_immutability.py`'s module docstring -- silently drops that
table's three hand-written raw-SQL immutability triggers unless the
migration explicitly recreates them. This file proves both halves: the
CHECK constraint itself rejects non-JSON `basis_ref` values and accepts
valid JSON at the database layer, and the three triggers are still present
at Alembic head after that migration's rebuild.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text

_EDITORIAL_APPROVALS_TRIGGERS = {
    "trg_editorial_approvals_no_update",
    "trg_editorial_approvals_no_delete",
    "trg_editorial_approvals_no_insert_replace",
}


def _new_id() -> str:
    return uuid.uuid4().hex


def _insert_version(connection, *, owner_id: str) -> str:
    version_id = _new_id()
    connection.execute(
        text(
            """
            INSERT INTO canonical_graph_versions
                (id, version_label, manifest_version, manifest_hash, status,
                 creator_owner_id, created_at, published_at, supersedes_version_id)
            VALUES
                (:id, :version_label, 'v1', :manifest_hash, 'authored',
                 :creator_owner_id, :created_at, NULL, NULL)
            """
        ),
        {
            "id": version_id,
            "version_label": f"fixture-{version_id}",
            "manifest_hash": f"hash-{version_id}",
            "creator_owner_id": owner_id,
            "created_at": now_text(SystemClock()),
        },
    )
    return version_id


def _insert_approval(
    connection, *, graph_version_id: str, owner_id: str, basis_ref: str
) -> str:
    approval_id = _new_id()
    connection.execute(
        text(
            """
            INSERT INTO editorial_approvals
                (id, graph_version_id, approver_owner_id, approver_role, basis_ref, approved_at)
            VALUES
                (:id, :graph_version_id, :approver_owner_id, 'designated_editorial_approver',
                 :basis_ref, :approved_at)
            """
        ),
        {
            "id": approval_id,
            "graph_version_id": graph_version_id,
            "approver_owner_id": owner_id,
            "basis_ref": basis_ref,
            "approved_at": now_text(SystemClock()),
        },
    )
    return approval_id


@pytest.fixture
def owner_id(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()
    return owner.id


def test_basis_ref_valid_trigger_survives_the_batch_alter_rebuild(
    engine: Engine,
) -> None:
    """`4747447ccaa3` rebuilds `editorial_approvals` via `op.batch_alter_table`
    to add the CHECK constraint; the table's three raw-SQL immutability
    triggers (`87af9746aec1`) are not part of `Base.metadata` and would be
    silently dropped by that rebuild unless explicitly recreated.
    """
    with engine.connect() as connection:
        names = set(
            connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'editorial_approvals'"
                )
            ).scalars()
        )
    missing = _EDITORIAL_APPROVALS_TRIGGERS - names
    assert not missing, (
        f"editorial_approvals is missing trigger(s) {sorted(missing)} at Alembic head"
    )


def test_non_json_basis_ref_is_rejected(engine: Engine, owner_id: str) -> None:
    with (
        pytest.raises(IntegrityError, match="basis_ref_valid"),
        engine.begin() as connection,
    ):
        version_id = _insert_version(connection, owner_id=owner_id)
        _insert_approval(
            connection,
            graph_version_id=version_id,
            owner_id=owner_id,
            basis_ref="fixture-approval-basis-v1",
        )


def test_valid_json_object_basis_ref_is_accepted(engine: Engine, owner_id: str) -> None:
    with engine.begin() as connection:
        version_id = _insert_version(connection, owner_id=owner_id)
        approval_id = _insert_approval(
            connection,
            graph_version_id=version_id,
            owner_id=owner_id,
            basis_ref='{"kind":"fixture-test","ref":"https://example.invalid/basis"}',
        )

    with engine.connect() as connection:
        basis_ref = connection.execute(
            text("SELECT basis_ref FROM editorial_approvals WHERE id = :id"),
            {"id": approval_id},
        ).scalar_one()
    assert basis_ref == '{"kind":"fixture-test","ref":"https://example.invalid/basis"}'

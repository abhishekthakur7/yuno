"""Integration tests proving NFR-03 audit-event immutability:
`audit_events` rejects UPDATE/DELETE both via the repository and via a
SQLite trigger.

Two independent layers:

- Repository layer: `SqlAlchemyAuditRepository` exposes no update/delete
  method at all, and `append` refuses to silently overwrite an existing id.
- Database layer: raw SQL, bypassing the repository entirely, proves SQLite
  itself (the migration's `trg_audit_events_no_update`/`_no_delete`/
  `_no_insert_replace` triggers) refuses UPDATE/DELETE/REPLACE even when the
  application layer is circumvented.

`trg_audit_events_no_update` and `trg_audit_events_no_delete` alone are
insufficient: SQLite's `INSERT OR REPLACE` resolves a PRIMARY KEY conflict
by deleting the conflicting row internally (no DELETE trigger fires unless
`recursive_triggers` is on, which it is not) and inserting the new values --
rewriting every column of a supposedly immutable row without ever using the
UPDATE or DELETE keyword. `trg_audit_events_no_insert_replace` (a BEFORE
INSERT existence guard) closes that gap; the tests below prove it.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.audit.repository import SqlAlchemyAuditRepository
from yuno.modules.identity.domain import Role
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import ConflictError
from yuno.shared.domain.ids import new_id

# Column order mirrors the migration's `op.create_table('audit_events', ...)`
# and `AuditEventRow` -- used to build raw INSERT statements that bypass the
# repository entirely (the database-layer tests below).
_AUDIT_EVENTS_COLUMNS = (
    "id",
    "owner_id",
    "goal_id",
    "actor_role",
    "entity_type",
    "entity_id",
    "action",
    "before_hash",
    "after_hash",
    "reason",
    "request_id",
    "correlation_id",
    "occurred_at",
)

_APPEND_ONLY_TRIGGERS = {
    "trg_audit_events_no_update",
    "trg_audit_events_no_delete",
    "trg_audit_events_no_insert_replace",
}


def _new_event(*, owner_id: str, event_id: str | None = None, reason: str | None = None) -> AuditEvent:
    return AuditEvent(
        id=event_id or new_id(),
        owner_id=owner_id,
        goal_id=None,
        actor_role=Role.LEARNER.value,
        entity_type="probe",
        entity_id="probe-1",
        action="probe_action",
        before_hash=None,
        after_hash=None,
        reason=reason,
        request_id=None,
        correlation_id=None,
        occurred_at=now_text(SystemClock()),
    )


def _row_values(event: AuditEvent) -> dict[str, Any]:
    """`event`'s fields keyed by column name, for raw-SQL params/comparison."""
    return {column: getattr(event, column) for column in _AUDIT_EVENTS_COLUMNS}


def _insert_sql(*, or_replace: bool = False, on_conflict_do_update: bool = False) -> str:
    assert not (or_replace and on_conflict_do_update)
    verb = "INSERT OR REPLACE" if or_replace else "INSERT"
    columns = ", ".join(_AUDIT_EVENTS_COLUMNS)
    placeholders = ", ".join(f":{column}" for column in _AUDIT_EVENTS_COLUMNS)
    sql = f"{verb} INTO audit_events ({columns}) VALUES ({placeholders})"
    if on_conflict_do_update:
        sql += " ON CONFLICT(id) DO UPDATE SET reason = excluded.reason"
    return sql


# --- Repository layer: no update/delete method; append refuses to overwrite ---


def test_audit_repository_exposes_no_update_or_delete_method() -> None:
    public_methods = {
        name
        for name, _ in inspect.getmembers(SqlAlchemyAuditRepository, predicate=inspect.isfunction)
        if not name.startswith("_")
    }

    forbidden = {"update", "delete", "remove", "edit", "modify", "patch", "set", "overwrite"}
    assert public_methods.isdisjoint(forbidden), (
        f"SqlAlchemyAuditRepository exposes mutating method(s): "
        f"{public_methods & forbidden}"
    )

    # Positive form of the same contract (spec §4.1): exactly these two
    # methods exist, full stop.
    assert public_methods == {"append", "list_for_owner"}


def test_append_with_duplicate_id_raises_conflict_error(uow_factory: UnitOfWorkFactory) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()

    event = _new_event(owner_id=owner.id, event_id=new_id(), reason="original")
    with uow_factory() as uow:
        uow.audit.append(event)
        uow.commit()

    duplicate = _new_event(owner_id=owner.id, event_id=event.id, reason="attempted overwrite")
    with uow_factory() as uow, pytest.raises(ConflictError):
        uow.audit.append(duplicate)

    # The rejected append must not have partially applied.
    with uow_factory() as uow:
        stored = uow.audit.list_for_owner(owner.id)
    assert len(stored) == 1
    assert stored[0].reason == "original"


# --- Database layer: raw SQL, bypassing the repository entirely ---


def test_database_trigger_rejects_raw_update(engine: Engine, uow_factory: UnitOfWorkFactory) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()

    event = _new_event(owner_id=owner.id, reason="original")
    with uow_factory() as uow:
        uow.audit.append(event)
        uow.commit()

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE audit_events SET reason = :reason WHERE id = :id"),
            {"reason": "hacked", "id": event.id},
        )

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT reason FROM audit_events WHERE id = :id"), {"id": event.id}
        ).one()
    assert row.reason == "original"


def test_database_trigger_rejects_raw_delete(engine: Engine, uow_factory: UnitOfWorkFactory) -> None:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()

    event = _new_event(owner_id=owner.id, reason="original")
    with uow_factory() as uow:
        uow.audit.append(event)
        uow.commit()

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": event.id})

    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE id = :id"), {"id": event.id}
        ).scalar()
    assert count == 1


def test_database_trigger_rejects_insert_or_replace(engine: Engine, uow_factory: UnitOfWorkFactory) -> None:
    """`INSERT OR REPLACE` resolves a PRIMARY KEY conflict by
    deleting-then-inserting internally, using neither UPDATE nor DELETE, so
    it bypasses the update/delete triggers alone.
    `trg_audit_events_no_insert_replace` must reject it and leave the
    original row byte-identical.
    """
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()

    original = _new_event(owner_id=owner.id, reason="original")
    with uow_factory() as uow:
        uow.audit.append(original)
        uow.commit()

    tampered = _new_event(owner_id=owner.id, event_id=original.id, reason="TAMPERED")
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(_insert_sql(or_replace=True)), _row_values(tampered))

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT * FROM audit_events WHERE id = :id"), {"id": original.id}
        ).mappings().one()
    assert dict(row) == _row_values(original)


def test_database_trigger_rejects_upsert_on_conflict_do_update(
    engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    """`INSERT ... ON CONFLICT(id) DO UPDATE` (a true SQLite upsert) is
    already rejected by `trg_audit_events_no_update`, since SQLite fires
    UPDATE triggers for the DO UPDATE action. Locked in here so a future
    change cannot silently regress it.
    """
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()

    original = _new_event(owner_id=owner.id, reason="original")
    with uow_factory() as uow:
        uow.audit.append(original)
        uow.commit()

    tampered = _new_event(owner_id=owner.id, event_id=original.id, reason="TAMPERED")
    upsert_sql = _insert_sql(on_conflict_do_update=True)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(upsert_sql), _row_values(tampered))

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT * FROM audit_events WHERE id = :id"), {"id": original.id}
        ).mappings().one()
    assert dict(row) == _row_values(original)


def test_database_trigger_allows_insert_of_fresh_id(engine: Engine, uow_factory: UnitOfWorkFactory) -> None:
    """Guard against `trg_audit_events_no_insert_replace` over-blocking: its
    `WHEN EXISTS (...)` guard must only fire for an id that already exists,
    never for an ordinary insert of a brand-new id.
    """
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()

    fresh = _new_event(owner_id=owner.id, reason="fresh")
    with engine.begin() as connection:
        connection.execute(text(_insert_sql()), _row_values(fresh))

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT reason FROM audit_events WHERE id = :id"), {"id": fresh.id}
        ).one()
    assert row.reason == "fresh"


def test_audit_events_append_only_triggers_exist_at_alembic_head(engine: Engine) -> None:
    """Tripwire, not a repository/business-logic test: `migrations/env.py`
    sets `render_as_batch=True`, and SQLite batch mode implements
    `ALTER TABLE` as rename -> recreate -> copy -> drop. Triggers are raw
    SQL, invisible to SQLAlchemy metadata, so a future
    `batch_alter_table("audit_events", ...)` migration would silently drop
    all three append-only triggers with no error at migration time. If this
    test fails, that migration must explicitly recreate them.
    """
    with engine.connect() as connection:
        names = set(
            connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'trigger' AND tbl_name = 'audit_events'"
                )
            ).scalars()
        )

    missing = _APPEND_ONLY_TRIGGERS - names
    assert not missing, (
        f"audit_events is missing append-only trigger(s) {sorted(missing)} at "
        "the current Alembic head. A batch-mode migration (SQLAlchemy "
        "`render_as_batch=True`, see migrations/env.py) most likely rebuilt "
        "the `audit_events` table and dropped them -- they must be "
        "recreated in that migration."
    )

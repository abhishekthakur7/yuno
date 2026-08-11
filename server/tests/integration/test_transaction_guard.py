"""Integration tests for the spec §3.4 write-transaction I/O boundary
(`yuno.shared.application.transaction_guard.guard_external_call`).

Nothing in the codebase performs external I/O yet (no provider/source/
runner adapters exist -- those are later tickets), so these tests simulate
one: a stand-in "external call" that starts with `guard_external_call(uow)`,
exactly as a real adapter will. The real `SqlAlchemyUnitOfWork` (composition
root, `yuno.unit_of_work`) backs `has_open_write_transaction()` via a
`Session.info` flag flipped by real SQLAlchemy `after_flush`/`after_commit`/
`after_rollback` events -- no mocking of the guard's own logic.
"""

from __future__ import annotations

import pytest

from yuno.shared.application.transaction_guard import (
    TransactionOpenError,
    guard_external_call,
)
from yuno.shared.application.unit_of_work import UnitOfWork, UnitOfWorkFactory


def _pretend_external_call(uow: UnitOfWork) -> str:
    guard_external_call(uow)
    return "external call executed"


def test_guard_raises_while_a_write_transaction_is_open(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        uow.owners.create_local_owner("Guard Probe")
        # `create_local_owner` above has already flushed an INSERT to
        # SQLite -- the exact write-lock window spec §3.4 forbids external
        # I/O inside -- but the transaction is not yet committed.
        with pytest.raises(TransactionOpenError):
            _pretend_external_call(uow)
        uow.commit()


def test_guard_allows_the_same_call_after_commit(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        uow.owners.create_local_owner("Guard Probe Committed")
        uow.commit()
        assert _pretend_external_call(uow) == "external call executed"


def test_guard_allows_the_same_call_after_rollback(
    uow_factory: UnitOfWorkFactory,
) -> None:
    with uow_factory() as uow:
        uow.owners.create_local_owner("Guard Probe Rolled Back")
        uow.rollback()
        assert _pretend_external_call(uow) == "external call executed"


def test_guard_does_not_fire_on_read_only_work(
    uow_factory: UnitOfWorkFactory,
) -> None:
    """A `with` block that only reads -- no repository write has flushed
    anything -- must never trip the guard, committed or not.
    """
    with uow_factory() as uow:
        uow.owners.create_local_owner("Read Fixture")
        uow.commit()

    with uow_factory() as uow:
        uow.owners.get_local_owner()
        assert _pretend_external_call(uow) == "external call executed"

"""The write-transaction I/O boundary guard (spec §3.4).

Spec §3.4: "External model, source and runner operations never execute
inside a SQLite write transaction." Until now this was convention only.
A held-open write transaction locks out every other SQLite writer for its
full duration -- a concurrent connection times out with "database is
locked" -- so a violation must FAIL loudly rather than merely be
discouraged.

This module owns only the guard itself: `TransactionOpenError` and
`guard_external_call`, which external-call sites (providers, sources,
runners -- none exist yet; later tickets' adapters call this) invoke
immediately before performing any external I/O. It depends on nothing but
`UnitOfWork`, so it stays framework-free per the "Domain and application
are framework-free" import-linter contract. Bookkeeping of *whether* a
write transaction is open is the concrete `SqlAlchemyUnitOfWork`'s job
(`yuno.unit_of_work`, the only place allowed to depend on SQLAlchemy) --
this module only asks via `UnitOfWork.has_open_write_transaction()` and
raises on `True`.
"""

from __future__ import annotations

from yuno.shared.application.unit_of_work import UnitOfWork


class TransactionOpenError(RuntimeError):
    """Raised by `guard_external_call` when a write transaction is open on
    the `UnitOfWork` passed to it.
    """


def guard_external_call(uow: UnitOfWork) -> None:
    """Raise `TransactionOpenError` if `uow` currently has an open write
    transaction; otherwise return without side effects.

    Call this as the first line of any external model/source/runner call
    site, passing the same `UnitOfWork` the surrounding command used. It is
    a no-op for read-only work (no writes yet flushed in the current
    transaction) and for calls made after `commit()`/`rollback()`.
    """
    if uow.has_open_write_transaction():
        raise TransactionOpenError(
            "Refusing external I/O: a write transaction is open on this "
            "UnitOfWork. Commit (or roll back) the transaction before "
            "performing external model, source or runner calls (spec §3.4)."
        )

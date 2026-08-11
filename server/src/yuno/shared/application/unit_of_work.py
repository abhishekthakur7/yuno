"""The minimal unit-of-work seam (spec §3.4).

Spec §3.4: one application `UnitOfWork` is used per HTTP command. External
model, source and runner operations never execute inside a SQLite write
transaction -- callers open the UoW, do repository work, commit, and only
then (outside the `with` block) perform any external call.

`has_open_write_transaction()` backs the `transaction_guard` module (same
package): it reports whether at least one write has been flushed in the
current transaction and not yet committed or rolled back, so external-call
sites can be refused entry (spec §3.4) while ordinary read-only work inside
a `with` block is left alone.

This protocol names NO module repository -- doing so would make
`yuno.shared` depend on `yuno.modules`, inverting spec §3.2's dependency
direction. Each module instead declares its own `<Module>UnitOfWork`
protocol extending this one with its own repository attribute(s), e.g.
`yuno.modules.identity.ports.IdentityUnitOfWork` adds `owners:
OwnerRepository`. The concrete `SqlAlchemyUnitOfWork` (`yuno.unit_of_work`,
the composition root -- it is the one place allowed to depend on every
module) wires every module's repository onto one object that satisfies
all of those protocols structurally at once.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self


class UnitOfWork(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def has_open_write_transaction(self) -> bool: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...

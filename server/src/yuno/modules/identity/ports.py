"""`identity` module ports (spec §3.3).

Protocols only -- no implementation lives here. `yuno.modules.identity.repository`
provides the SQLAlchemy-backed adapter that satisfies `OwnerRepository`
structurally.
"""

from __future__ import annotations

from typing import Protocol

from yuno.modules.identity.domain import Owner, Role
from yuno.shared.application.unit_of_work import UnitOfWork


class OwnerRepository(Protocol):
    def get_local_owner(self) -> Owner | None: ...

    def create_local_owner(self, display_name: str) -> Owner: ...

    def grants(self, owner_id: str) -> frozenset[Role]: ...

    def grant_role(self, owner_id: str, role: Role, assigned_by_owner_id: str) -> None: ...


class IdentityUnitOfWork(UnitOfWork, Protocol):
    """A `UnitOfWork` that also carries the `identity` module's repository.

    A route/service depending only on this (rather than the concrete
    `yuno.unit_of_work.SqlAlchemyUnitOfWork`) can use `uow.owners` without
    knowing anything about other modules' repositories.
    """

    owners: OwnerRepository

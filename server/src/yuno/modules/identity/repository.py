"""SQLAlchemy adapter for `OwnerRepository` (spec §4.2).

Maps `OwnerRow`/`OwnerRoleGrantRow` to/from the frozen `Owner` domain
dataclass; ORM rows never cross the repository boundary. `owners` itself
carries no `owner_id` column (see `shared.infrastructure.base.OWNERLESS_TABLES`)
because a row's own `id` *is* the owner id. `owner_role_grants` is
owner-owned, so `grants`/`grant_role` go through `owner_scoped_select`.

`create_local_owner` translates a concurrent-create race (SQLite's
`UNIQUE` constraint on `owners.kind` rejecting a second singleton row)
from `sqlalchemy.exc.IntegrityError` into the domain's `ConflictError` --
`yuno.modules.identity.domain`/`.ports`/`.service` cannot import
SQLAlchemy (spec §3.2, import-linter enforced), so this translation has
to happen here, at the boundary. `service.ensure_local_owner` is the
caller that catches it and makes the whole operation idempotent under
concurrency.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from yuno.modules.identity.domain import Owner, OwnerKind, OwnerStatus, Role
from yuno.modules.identity.models import OwnerRoleGrantRow, OwnerRow
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import ConflictError
from yuno.shared.domain.ids import new_id
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyOwnerRepository(SqlAlchemyRepository):
    """`OwnerRepository` adapter (satisfied structurally, per
    `ports.py`'s docstring -- no explicit Protocol inheritance).
    """

    __slots__ = ("_clock",)

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        # `shared.domain.clock` is used directly (not injected) -- the
        # `OwnerRepository` protocol has no clock parameter, so timestamp
        # generation is this repository's own responsibility.
        self._clock = SystemClock()

    def get_local_owner(self) -> Owner | None:
        stmt = select(OwnerRow).where(OwnerRow.kind == OwnerKind.LOCAL_BUILTIN.value)
        row = self._session.scalars(stmt).one_or_none()
        return _to_domain(row) if row is not None else None

    def create_local_owner(self, display_name: str) -> Owner:
        """Insert and return a new local-owner row.

        Raises `ConflictError` if a concurrent caller has already created
        the singleton `kind='local_builtin'` row (translated from the
        database's `IntegrityError` -- see module docstring). That leaves
        this method's flush unresolved; the caller's UoW must be rolled
        back before it can be used again, which is exactly what
        `ensure_local_owner` does before re-reading the winner's row.
        """
        row = OwnerRow(
            id=new_id(),
            kind=OwnerKind.LOCAL_BUILTIN.value,
            display_name=display_name,
            status=OwnerStatus.ACTIVE.value,
            created_at=now_text(self._clock),
        )
        self._session.add(row)
        try:
            # Flush (not just add): the session factory disables autoflush, so
            # a caller that immediately reads this row back (e.g. `grants`,
            # or a second `get_local_owner`) within the same UoW would
            # otherwise miss it.
            self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("Local owner already exists.") from exc
        return _to_domain(row)

    def grants(self, owner_id: str) -> frozenset[Role]:
        stmt = owner_scoped_select(OwnerRoleGrantRow, owner_id)
        rows = self._session.scalars(stmt).all()
        return frozenset(Role(row.role) for row in rows)

    def grant_role(self, owner_id: str, role: Role, assigned_by_owner_id: str) -> None:
        row = OwnerRoleGrantRow(
            owner_id=owner_id,
            role=role.value,
            assigned_at=now_text(self._clock),
            assigned_by_owner_id=assigned_by_owner_id,
        )
        self._session.add(row)
        self._session.flush()


def _to_domain(row: OwnerRow) -> Owner:
    return Owner(
        id=row.id,
        kind=OwnerKind(row.kind),
        display_name=row.display_name,
        status=OwnerStatus(row.status),
        created_at=row.created_at,
    )

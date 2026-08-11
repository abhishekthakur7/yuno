"""SQLAlchemy adapter for `AuditRepository` (spec §4.7, §4.1).

Exposes only `append` and `list_for_owner` -- intentionally no update or
delete. `append`'s refusal to overwrite an existing `id` is the first
line of defence for the `audit_events` append-only guarantee; the SQLite
triggers (owned by the migrations) are the second (ticket: "`audit_events`
append-only, rejecting UPDATE/DELETE via repository and SQLite trigger").
Maps `AuditEventRow` to/from the frozen `AuditEvent` domain dataclass; ORM
rows never cross the repository boundary.
"""

from __future__ import annotations

from collections.abc import Sequence

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.audit.models import AuditEventRow
from yuno.shared.domain.errors import ConflictError
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyAuditRepository(SqlAlchemyRepository):
    """`AuditRepository` adapter (satisfied structurally, per
    `ports.py`'s docstring -- no explicit Protocol inheritance).
    """

    __slots__ = ()

    def append(self, event: AuditEvent) -> None:
        """Persist `event`. Raises `ConflictError` if `event.id` already exists.

        Deliberately a bare `session.get(AuditEventRow, event.id)` primary-key
        lookup, not `owner_scoped_select`: `audit_events.id` is the table's
        actual `PRIMARY KEY`, a globally unique ULID, not scoped per owner --
        so a same-id collision is a real conflict regardless of which owner
        generated it.
        """
        if self._session.get(AuditEventRow, event.id) is not None:
            raise ConflictError(f"Audit event '{event.id}' already exists.")
        self._session.add(_to_row(event))
        # Flush (not just add): the session factory disables autoflush,
        # so a subsequent `append`/`list_for_owner` in the same UoW would
        # otherwise not see this row yet.
        self._session.flush()

    def list_for_owner(self, owner_id: str, limit: int = 100) -> Sequence[AuditEvent]:
        stmt = (
            owner_scoped_select(AuditEventRow, owner_id)
            .order_by(AuditEventRow.occurred_at.desc())
            .limit(limit)
        )
        rows = self._session.scalars(stmt).all()
        return [_to_domain(row) for row in rows]


def _to_row(event: AuditEvent) -> AuditEventRow:
    return AuditEventRow(
        id=event.id,
        owner_id=event.owner_id,
        goal_id=event.goal_id,
        actor_role=event.actor_role,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        action=event.action,
        before_hash=event.before_hash,
        after_hash=event.after_hash,
        reason=event.reason,
        request_id=event.request_id,
        correlation_id=event.correlation_id,
        occurred_at=event.occurred_at,
    )


def _to_domain(row: AuditEventRow) -> AuditEvent:
    return AuditEvent(
        id=row.id,
        owner_id=row.owner_id,
        goal_id=row.goal_id,
        actor_role=row.actor_role,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        action=row.action,
        before_hash=row.before_hash,
        after_hash=row.after_hash,
        reason=row.reason,
        request_id=row.request_id,
        correlation_id=row.correlation_id,
        occurred_at=row.occurred_at,
    )

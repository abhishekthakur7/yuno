"""`audit` module ports (spec §3.3).

Protocols only -- no implementation lives here. `yuno.modules.audit.repository`
provides the SQLAlchemy-backed adapter that satisfies `AuditRepository`
structurally.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from yuno.modules.audit.domain import AuditEvent
from yuno.shared.application.unit_of_work import UnitOfWork


class AuditRepository(Protocol):
    """Append-only: intentionally exposes no update or delete method."""

    def append(self, event: AuditEvent) -> None: ...

    def list_for_owner(self, owner_id: str, limit: int = 100) -> Sequence[AuditEvent]: ...


class AuditUnitOfWork(UnitOfWork, Protocol):
    """A `UnitOfWork` that also carries the `audit` module's repository."""

    audit: AuditRepository

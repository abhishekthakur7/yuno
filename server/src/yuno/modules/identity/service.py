"""Identity use cases (spec §4.2; PRD §14 Q2).

Framework-free, like the rest of `yuno.modules.identity`'s `domain.py`/
`ports.py`: only the standard library, `yuno.shared.domain`,
`yuno.shared.application`, `yuno.modules.identity.*` and (see below)
`yuno.modules.audit.*` may be imported here -- no SQLAlchemy, FastAPI or
Pydantic. An import-linter architecture test enforces this.

`ensure_local_owner` depends on `yuno.modules.audit.ports` (`AuditRepository`,
via `_EnsureLocalOwnerUnitOfWork` below) because creating the local owner
also appends one audit event. That is the one legitimate identity->audit
edge the module-independence contract allows -- `audit` is cross-cutting
(spec §3.3/IDK-101: "applies to every module"), so any module, including
identity, may depend on it; see `pyproject.toml`'s independence contract
and `yuno.modules`'s docstring.
"""

from __future__ import annotations

from typing import Protocol

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.audit.ports import AuditRepository
from yuno.modules.identity.domain import Owner, Role
from yuno.modules.identity.ports import IdentityUnitOfWork
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import ConflictError
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


class _EnsureLocalOwnerUnitOfWork(IdentityUnitOfWork, Protocol):
    """The narrow slice of the composition-root `UnitOfWork` this function
    needs: the `identity` module's own `owners` repository, plus the
    cross-cutting `audit` module's `audit` repository for the creation
    event this function appends.
    """

    audit: AuditRepository


def ensure_local_owner(
    uow: _EnsureLocalOwnerUnitOfWork,
    display_name: str,
    clock: Clock | None = None,
) -> Owner:
    """Idempotently resolve the singleton `kind='local_builtin'` owner.

    On first call: creates the owner, grants it both `Role.LEARNER` and
    `Role.DESIGNATED_EDITORIAL_APPROVER` as distinct grant rows (PRD §14
    Q2 -- for MVP the local owner is the designated editorial approver;
    spec §4.2 D1 -- the roles stay distinct rows even though one owner
    holds both), and appends one `AuditEvent` recording the creation. On
    every later call the owner already exists and is returned as-is --
    existence of the owner *is* the idempotency check.

    Concurrency-safe: if two callers race, SQLite's `UNIQUE` constraint
    on `owners.kind` lets exactly one `create_local_owner` call succeed;
    every other call raises `ConflictError` (translated from
    `IntegrityError` inside `SqlAlchemyOwnerRepository`, so this
    framework-free module never sees the SQLAlchemy type). The losing
    caller rolls its own UoW back -- clearing the failed flush so the
    session is usable again -- and re-reads the winner's committed row.

    The creation audit event's `actor_role` is recorded as
    `designated_editorial_approver` rather than `learner`, per the
    spec's precedent for how the local owner's actions are attributed
    (spec §6.1 step 3).

    `clock`, if given, is used only for that audit event's `occurred_at`
    (defaults to the system clock); the owner/grant rows' own timestamps
    come from the repository independently of this parameter.

    Does not commit -- the caller owns `uow`'s lifecycle. The internal
    `uow.rollback()` on a lost create race only discards this function's
    own not-yet-committed work; every real call site opens a UoW
    dedicated to this call.
    """
    existing = uow.owners.get_local_owner()
    if existing is not None:
        return existing

    try:
        owner = uow.owners.create_local_owner(display_name)
    except ConflictError:
        uow.rollback()
        owner = uow.owners.get_local_owner()
        if owner is None:
            # The conflict said the row exists but it's still not visible
            # after rollback -- something other than the expected create
            # race caused this; don't paper over it.
            raise
        return owner

    uow.owners.grant_role(owner.id, Role.LEARNER, assigned_by_owner_id=owner.id)
    uow.owners.grant_role(
        owner.id, Role.DESIGNATED_EDITORIAL_APPROVER, assigned_by_owner_id=owner.id
    )

    resolved_clock = clock if clock is not None else SystemClock()
    uow.audit.append(
        AuditEvent(
            id=new_id(),
            owner_id=owner.id,
            goal_id=None,
            actor_role=Role.DESIGNATED_EDITORIAL_APPROVER.value,
            entity_type="owner",
            entity_id=owner.id,
            action="local_owner_created",
            before_hash=None,
            after_hash=hash_payload(
                {
                    "id": owner.id,
                    "kind": owner.kind.value,
                    "display_name": owner.display_name,
                    "status": owner.status.value,
                    "roles": sorted(
                        [Role.LEARNER.value, Role.DESIGNATED_EDITORIAL_APPROVER.value]
                    ),
                }
            ),
            reason="Local owner created and granted MVP roles.",
            request_id=None,
            correlation_id=None,
            occurred_at=now_text(resolved_clock),
        )
    )
    return owner

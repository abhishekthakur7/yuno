"""Shared infrastructure for SQLAlchemy-backed repository adapters.

`_session` is private (not `self.session`) because a public session let a
caller holding a `UnitOfWork` reach through a repository to read or write
directly (e.g. `uow.audit.session.get(AuditEventRow, some_id)`), bypassing
every owner-scoped method and the `owner_id` filter. `__slots__` (on this
class and every module's concrete repository) turns any attempt to
resurrect that attribute -- or any other undeclared one -- into an
`AttributeError` rather than a silent success.

Python has no true private attributes, so this is convention, not a
language-level guarantee: code that reaches `_session` directly can still
hand-roll an unscoped query. What actually holds the ticket's
owner-isolation acceptance criterion ("a record written under owner A is
unreachable through any repository call scoped to owner B") is that every
owner-owned read/write in each module's `repository.py` goes through
`owner_scoped_select` below, verified by `test_owner_isolation.py`'s
behavioural tests. `owner_scoped_select` centralizes the `owner_id`
filter so those methods share one tested filter instead of hand-rolling
`.where(...)` per call site.

Intentionally small: this is not a generic repository framework, just the
one thing every module's repository would otherwise duplicate.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session


class SqlAlchemyRepository:
    """Base class for SQLAlchemy-backed repository adapters.

    `_session` is private by convention (see module docstring) and by
    `__slots__`: subclasses must declare their own `__slots__` (even if
    empty) to keep the no-`__dict__`/no-stray-attribute guarantee.
    """

    __slots__ = ("_session",)

    def __init__(self, session: Session) -> None:
        self._session = session


def owner_scoped_select(model: type[Any], owner_id: str) -> Select[Any]:
    """`SELECT * FROM model WHERE model.owner_id == owner_id`.

    `model` must be a mapped class declaring an `owner_id` column (every
    owner-owned ORM row has one, per spec §4.1).
    """
    return select(model).where(model.owner_id == owner_id)

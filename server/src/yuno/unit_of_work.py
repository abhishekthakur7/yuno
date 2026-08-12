"""The concrete `UnitOfWork` composition root (spec §3.4).

One SQLAlchemy `Session` -- and thus one SQLite transaction -- per `with`
block, wiring every module's repository onto that one object so it
structurally satisfies every module's `<Module>UnitOfWork` protocol
(`yuno.modules.identity.ports.IdentityUnitOfWork`,
`yuno.modules.audit.ports.AuditUnitOfWork`, ...) at once.

Deliberately NOT under `yuno.shared`: wiring every module's repository
together requires importing every module, which `yuno.shared` must never
do (see that package's docstring on the dependency-inversion trap this
avoids). It also isn't under any one `yuno.modules.*` package, since it
depends on all of them -- `yuno.api` is the only caller.

External model, source and runner operations never execute inside the
SQLite write transaction this class opens -- callers do all repository
work inside the `with` block, call `commit()`, and only then, outside the
block, perform any external call.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.audit.repository import SqlAlchemyAuditRepository
from yuno.modules.canonical.ports import CanonicalGraphRepository
from yuno.modules.canonical.repository import SqlAlchemyCanonicalRepository
from yuno.modules.diagnostics.ports import DiagnosticsRepository
from yuno.modules.diagnostics.repository import SqlAlchemyDiagnosticsRepository
from yuno.modules.evidence_evaluation.ports import EvidenceRepository
from yuno.modules.evidence_evaluation.repository import SqlAlchemyEvidenceRepository
from yuno.modules.identity.ports import OwnerRepository
from yuno.modules.identity.repository import SqlAlchemyOwnerRepository
from yuno.modules.profiles_goals.ports import ProfilesGoalsRepository
from yuno.modules.profiles_goals.repository import SqlAlchemyProfilesGoalsRepository
from yuno.modules.roadmap.ports import RoadmapRepository
from yuno.modules.roadmap.repository import SqlAlchemyRoadmapRepository
from yuno.shared.application.unit_of_work import UnitOfWork, UnitOfWorkFactory

_WRITE_OPEN_KEY = "yuno_write_transaction_open"
"""`Session.info` key backing `SqlAlchemyUnitOfWork.has_open_write_transaction`
(spec §3.4 / `yuno.shared.application.transaction_guard`). `Session.info` is
a plain per-`Session` dict that survives flushes -- unlike `session.new`/
`dirty`/`deleted`, which are cleared by the flush that sends them to
SQLite -- and is fresh on every new `Session` from `sessionmaker()`, so no
explicit reset is needed between `with` blocks.
"""


def _mark_write_open(session: Session, _flush_context: object) -> None:
    """`after_flush` fires only when the flush actually sent INSERT/UPDATE/
    DELETE statements (SQLAlchemy short-circuits a no-op flush before
    emitting this event), so this only marks the transaction "open" once a
    real write has happened -- exactly the SQLite write-lock window spec
    §3.4 forbids external I/O inside.
    """
    session.info[_WRITE_OPEN_KEY] = True


def _mark_write_closed(session: Session) -> None:
    session.info[_WRITE_OPEN_KEY] = False


class SqlAlchemyUnitOfWork:
    """`UnitOfWork` adapter (satisfied structurally, per each module's
    `ports.py` docstring -- no explicit Protocol inheritance): one
    SQLAlchemy `Session`, and thus one SQLite transaction, per `with`
    block.
    """

    owners: OwnerRepository
    audit: AuditRepository
    canonical: CanonicalGraphRepository
    diagnostics: DiagnosticsRepository
    evidence: EvidenceRepository
    profiles_goals: ProfilesGoalsRepository
    roadmap: RoadmapRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._committed = False

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self._committed = False
        self._session.info[_WRITE_OPEN_KEY] = False
        event.listen(self._session, "after_flush", _mark_write_open)
        event.listen(self._session, "after_commit", _mark_write_closed)
        event.listen(self._session, "after_rollback", _mark_write_closed)
        self.owners = SqlAlchemyOwnerRepository(self._session)
        self.audit = SqlAlchemyAuditRepository(self._session)
        self.canonical = SqlAlchemyCanonicalRepository(self._session)
        self.diagnostics = SqlAlchemyDiagnosticsRepository(self._session)
        self.evidence = SqlAlchemyEvidenceRepository(self._session)
        self.profiles_goals = SqlAlchemyProfilesGoalsRepository(self._session)
        self.roadmap = SqlAlchemyRoadmapRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Roll back (unless committed) and always close the session.

        If `rollback()` itself fails, that failure must never replace an
        exception already propagating out of the `with` block -- e.g. a
        route's `NotFoundError`, which must reach the caller as a typed
        404, not a generic 500 because cleanup also went wrong. So the
        original exception always wins; the rollback failure is attached
        to it as a note instead of vanishing silently (there is no
        logging framework in this codebase to send it to). With no
        original exception, the rollback failure simply propagates.
        """
        session = self._require_session()
        try:
            if not self._committed:
                try:
                    session.rollback()
                except Exception as rollback_exc:
                    if exc is None:
                        raise
                    exc.add_note(
                        "UnitOfWork.__exit__: session.rollback() also "
                        f"failed while handling the above exception: {rollback_exc!r}"
                    )
        finally:
            session.close()
            self._session = None

    def commit(self) -> None:
        session = self._require_session()
        session.commit()
        self._committed = True

    def rollback(self) -> None:
        session = self._require_session()
        session.rollback()
        self._committed = False

    def has_open_write_transaction(self) -> bool:
        """Back `yuno.shared.application.transaction_guard.guard_external_call`
        (spec §3.4): `True` once a write has been flushed in the current
        transaction and neither `commit()` nor `rollback()` has run since.
        """
        session = self._require_session()
        return bool(session.info.get(_WRITE_OPEN_KEY, False))

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError(
                "SqlAlchemyUnitOfWork used outside its 'with' block — enter "
                "it first: 'with SqlAlchemyUnitOfWork(...) as uow: ...'."
            )
        return self._session


def create_unit_of_work_factory(
    session_factory: sessionmaker[Session],
) -> UnitOfWorkFactory:
    """Return a zero-arg callable that builds a fresh `SqlAlchemyUnitOfWork`
    bound to `session_factory` on every call (spec §3.4: one UoW per HTTP
    command -- a caller invokes this factory once per command, uses the
    result in a single `with` block, and discards it).
    """

    def factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    return factory

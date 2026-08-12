"""Concrete composition root for repositories sharing one SQLAlchemy session.

External operations must stay outside an open SQLite write transaction.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from yuno.modules.audit.ports import AuditRepository
from yuno.modules.audit.repository import SqlAlchemyAuditRepository
from yuno.modules.canonical.ports import (
    CanonicalGraphRepository,
    CanonicalMergeRepository,
)
from yuno.modules.canonical.repository import (
    SqlAlchemyCanonicalMergeRepository,
    SqlAlchemyCanonicalRepository,
)
from yuno.modules.diagnostics.ports import DiagnosticsRepository
from yuno.modules.diagnostics.repository import SqlAlchemyDiagnosticsRepository
from yuno.modules.evidence_evaluation.ports import EvidenceRepository
from yuno.modules.evidence_evaluation.repository import SqlAlchemyEvidenceRepository
from yuno.modules.hands_on.ports import HandsOnRepository
from yuno.modules.hands_on.repository import SqlAlchemyHandsOnRepository
from yuno.modules.identity.ports import OwnerRepository
from yuno.modules.identity.repository import SqlAlchemyOwnerRepository
from yuno.modules.imports.ports import ImportRepository
from yuno.modules.imports.repository import SqlAlchemyImportRepository
from yuno.modules.interview.repository import SqlAlchemyInterviewRepository
from yuno.modules.learning_content.ports import LearningContentRepository
from yuno.modules.learning_content.repository import SqlAlchemyLearningContentRepository
from yuno.modules.notebook_review.ports import NotebookReviewRepository
from yuno.modules.notebook_review.repository import SqlAlchemyNotebookReviewRepository
from yuno.modules.profiles_goals.ports import ProfilesGoalsRepository
from yuno.modules.profiles_goals.repository import SqlAlchemyProfilesGoalsRepository
from yuno.modules.provenance.ports import SourceRepository
from yuno.modules.provenance.repository import SqlAlchemySourceRepository
from yuno.modules.provider.ports import ProviderRepository
from yuno.modules.provider.repository import SqlAlchemyProviderRepository
from yuno.modules.roadmap.ports import RoadmapRepository
from yuno.modules.roadmap.repository import SqlAlchemyRoadmapRepository
from yuno.modules.settings_data.ports import SettingsRepository
from yuno.modules.settings_data.repository import SqlAlchemySettingsRepository
from yuno.shared.application.unit_of_work import UnitOfWork, UnitOfWorkFactory

_WRITE_OPEN_KEY = "yuno_write_transaction_open"


def _mark_write_open(session: Session, _flush_context: object) -> None:
    """Mark the external-I/O guard only after a real write flushes."""
    session.info[_WRITE_OPEN_KEY] = True


def _mark_write_closed(session: Session) -> None:
    session.info[_WRITE_OPEN_KEY] = False


class SqlAlchemyUnitOfWork:
    owners: OwnerRepository
    audit: AuditRepository
    canonical: CanonicalGraphRepository
    canonical_merges: CanonicalMergeRepository
    diagnostics: DiagnosticsRepository
    evidence: EvidenceRepository
    hands_on: HandsOnRepository
    imports: ImportRepository
    interview: SqlAlchemyInterviewRepository
    learning_content: LearningContentRepository
    notebook_review: NotebookReviewRepository
    profiles_goals: ProfilesGoalsRepository
    provenance: SourceRepository
    provider: ProviderRepository
    roadmap: RoadmapRepository
    settings_data: SettingsRepository

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        *,
        session: Session | None = None,
        flush_only: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._session: Session | None = session
        self._external_session = session
        self._flush_only = flush_only
        self._savepoint = None
        self._committed = False

    def __enter__(self) -> Self:
        if self._external_session is None:
            assert self._session_factory is not None
            self._session = self._session_factory()
        else:
            self._session = self._external_session
            self._savepoint = self._session.begin_nested()
        self._committed = False
        self._session.info[_WRITE_OPEN_KEY] = False
        event.listen(self._session, "after_flush", _mark_write_open)
        event.listen(self._session, "after_commit", _mark_write_closed)
        event.listen(self._session, "after_rollback", _mark_write_closed)
        self.owners = SqlAlchemyOwnerRepository(self._session)
        self.audit = SqlAlchemyAuditRepository(self._session)
        self.canonical = SqlAlchemyCanonicalRepository(self._session)
        self.canonical_merges = SqlAlchemyCanonicalMergeRepository(self._session)
        self.diagnostics = SqlAlchemyDiagnosticsRepository(self._session)
        self.evidence = SqlAlchemyEvidenceRepository(self._session)
        self.hands_on = SqlAlchemyHandsOnRepository(self._session)
        self.imports = SqlAlchemyImportRepository(self._session)
        self.interview = SqlAlchemyInterviewRepository(self._session)
        self.learning_content = SqlAlchemyLearningContentRepository(self._session)
        self.notebook_review = SqlAlchemyNotebookReviewRepository(self._session)
        self.profiles_goals = SqlAlchemyProfilesGoalsRepository(self._session)
        self.provenance = SqlAlchemySourceRepository(self._session)
        self.provider = SqlAlchemyProviderRepository(self._session)
        self.roadmap = SqlAlchemyRoadmapRepository(self._session)
        self.settings_data = SqlAlchemySettingsRepository(self._session)
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
                    if (
                        self._external_session is not None
                        and self._savepoint is not None
                    ):
                        self._savepoint.rollback()
                    else:
                        session.rollback()
                except Exception as rollback_exc:
                    if exc is None:
                        raise
                    exc.add_note(
                        "UnitOfWork.__exit__: session.rollback() also "
                        f"failed while handling the above exception: {rollback_exc!r}"
                    )
        finally:
            if self._external_session is None:
                session.close()
                self._session = None

    def commit(self) -> None:
        session = self._require_session()
        if self._external_session is None and not self._flush_only:
            session.commit()
        else:
            session.flush()
            if self._savepoint is not None:
                self._savepoint.commit()
        self._committed = True

    def rollback(self) -> None:
        session = self._require_session()
        session.rollback()
        self._committed = False

    def has_open_write_transaction(self) -> bool:
        """Whether a write has been flushed since the last commit or rollback."""
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
    """Build a fresh unit of work for each command."""

    def factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    return factory


def create_transaction_unit_of_work_factory(session: Session) -> UnitOfWorkFactory:
    """Compose repositories on a dispatcher-owned terminal transaction.

    Module services may keep their normal UoW boundaries, but `commit()` only
    flushes. The dispatcher alone commits or rolls back domain output together
    with the authoritative JobResult and terminal event.
    """

    def factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session=session)

    return factory


def create_probe_unit_of_work_factory(
    session_factory: sessionmaker[Session],
) -> UnitOfWorkFactory:
    """Run read/validation code while rolling back provisional writes on close."""

    def factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory, flush_only=True)

    return factory

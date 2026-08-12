"""Owner-scoped SQLAlchemy adapter for profile and goal persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import update
from sqlalchemy.orm import Session

from yuno.modules.profiles_goals.domain import (
    GoalNavigationEvent,
    GoalPath,
    GoalStatus,
    GoalWorkspace,
    IdempotencyRecord,
    LearnerProfile,
    RecommendationDismissal,
    ResumeDestination,
    TargetCapability,
    TargetLevel,
)
from yuno.modules.profiles_goals.models import (
    GoalNavigationEventRow,
    GoalWorkspaceRow,
    LearnerProfileRow,
    ProfilesGoalsIdempotencyRow,
    RecommendationDismissalRow,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyProfilesGoalsRepository(SqlAlchemyRepository):
    __slots__ = ("_clock",)

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._clock = SystemClock()

    def get_profile(self, owner_id: str) -> LearnerProfile | None:
        row = self._session.scalars(
            owner_scoped_select(LearnerProfileRow, owner_id)
        ).one_or_none()
        return _profile(row) if row is not None else None

    def create_profile(self, owner_id: str) -> LearnerProfile:
        row = LearnerProfileRow(owner_id=owner_id, updated_at=now_text(self._clock))
        self._session.add(row)
        self._session.flush()
        return _profile(row)

    def update_profile(
        self, owner_id: str, expected_revision: int, changes: Mapping[str, object]
    ) -> LearnerProfile | None:
        values = dict(changes)
        values.update(
            profile_revision=expected_revision + 1, updated_at=now_text(self._clock)
        )
        result = self._session.execute(
            update(LearnerProfileRow)
            .where(
                LearnerProfileRow.owner_id == owner_id,
                LearnerProfileRow.profile_revision == expected_revision,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        row = self._session.scalars(
            owner_scoped_select(LearnerProfileRow, owner_id)
        ).one()
        return _profile(row)

    def list_goals(self, owner_id: str) -> Sequence[GoalWorkspace]:
        stmt = (
            owner_scoped_select(GoalWorkspaceRow, owner_id)
            .where(GoalWorkspaceRow.status != "tombstoned")
            .order_by(GoalWorkspaceRow.updated_at.desc())
        )
        return tuple(_goal(row) for row in self._session.scalars(stmt).all())

    def get_goal(self, owner_id: str, goal_id: str) -> GoalWorkspace | None:
        stmt = owner_scoped_select(GoalWorkspaceRow, owner_id).where(
            GoalWorkspaceRow.id == goal_id, GoalWorkspaceRow.status != "tombstoned"
        )
        row = self._session.scalars(stmt).one_or_none()
        return _goal(row) if row is not None else None

    def get_goal_for_lifecycle(
        self, owner_id: str, goal_id: str
    ) -> GoalWorkspace | None:
        row = self._session.scalars(
            owner_scoped_select(GoalWorkspaceRow, owner_id).where(
                GoalWorkspaceRow.id == goal_id
            )
        ).one_or_none()
        return _goal(row) if row is not None else None

    def create_goal(self, goal: GoalWorkspace) -> GoalWorkspace:
        row = GoalWorkspaceRow(
            id=goal.id,
            owner_id=goal.owner_id,
            name=goal.name,
            path=goal.path.value,
            subject=goal.subject,
            role=goal.role,
            target_level=goal.target_level.value,
            target_capability=goal.target_capability,
            graph_version_id=goal.graph_version_id,
            status=goal.status.value,
            resume_position=goal.resume_position,
            last_accessed_at=goal.last_accessed_at,
            row_version=goal.row_version,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
        )
        self._session.add(row)
        self._session.flush()
        return _goal(row)

    def tombstone_goal(
        self, owner_id: str, goal_id: str, expected_version: int
    ) -> GoalWorkspace | None:
        result = self._session.execute(
            update(GoalWorkspaceRow)
            .where(
                GoalWorkspaceRow.owner_id == owner_id,
                GoalWorkspaceRow.id == goal_id,
                GoalWorkspaceRow.row_version == expected_version,
                GoalWorkspaceRow.status != "tombstoned",
            )
            .values(
                status="tombstoned",
                row_version=expected_version + 1,
                updated_at=now_text(self._clock),
            )
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        return self.get_goal_for_lifecycle(owner_id, goal_id)

    def update_goal(
        self,
        owner_id: str,
        goal_id: str,
        expected_version: int,
        changes: Mapping[str, object],
    ) -> GoalWorkspace | None:
        values = dict(changes)
        values.update(
            row_version=expected_version + 1, updated_at=now_text(self._clock)
        )
        result = self._session.execute(
            update(GoalWorkspaceRow)
            .where(
                GoalWorkspaceRow.owner_id == owner_id,
                GoalWorkspaceRow.id == goal_id,
                GoalWorkspaceRow.row_version == expected_version,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        return self.get_goal(owner_id, goal_id)

    def append_navigation(self, event: GoalNavigationEvent) -> None:
        self._session.add(GoalNavigationEventRow(**event.__dict__))
        self._session.flush()

    def list_navigation(
        self, owner_id: str, goal_id: str
    ) -> Sequence[GoalNavigationEvent]:
        stmt = (
            owner_scoped_select(GoalNavigationEventRow, owner_id)
            .where(GoalNavigationEventRow.goal_id == goal_id)
            .order_by(
                GoalNavigationEventRow.occurred_at,
                GoalNavigationEventRow.id,
            )
        )
        return tuple(
            GoalNavigationEvent(
                id=row.id,
                owner_id=row.owner_id,
                goal_id=row.goal_id,
                position=row.position,
                destination=ResumeDestination(row.destination),
                occurred_at=row.occurred_at,
            )
            for row in self._session.scalars(stmt).all()
        )

    def add_dismissal(self, dismissal: RecommendationDismissal) -> bool:
        existing = self._session.scalars(
            owner_scoped_select(RecommendationDismissalRow, dismissal.owner_id).where(
                RecommendationDismissalRow.goal_id == dismissal.goal_id,
                RecommendationDismissalRow.recommendation_key
                == dismissal.recommendation_key,
            )
        ).one_or_none()
        if existing is None:
            self._session.add(RecommendationDismissalRow(**dismissal.__dict__))
            self._session.flush()
            return True
        return False

    def list_dismissals(
        self, owner_id: str, goal_id: str
    ) -> Sequence[RecommendationDismissal]:
        stmt = (
            owner_scoped_select(RecommendationDismissalRow, owner_id)
            .where(RecommendationDismissalRow.goal_id == goal_id)
            .order_by(RecommendationDismissalRow.dismissed_at)
        )
        return tuple(
            RecommendationDismissal(
                id=row.id,
                owner_id=row.owner_id,
                goal_id=row.goal_id,
                recommendation_key=row.recommendation_key,
                dismissed_at=row.dismissed_at,
            )
            for row in self._session.scalars(stmt).all()
        )

    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> IdempotencyRecord | None:
        row = self._session.scalars(
            owner_scoped_select(ProfilesGoalsIdempotencyRow, owner_id).where(
                ProfilesGoalsIdempotencyRow.operation == operation,
                ProfilesGoalsIdempotencyRow.idempotency_key == key,
            )
        ).one_or_none()
        if row is None:
            return None
        return IdempotencyRecord(
            id=row.id,
            owner_id=row.owner_id,
            operation=row.operation,
            idempotency_key=row.idempotency_key,
            request_hash=row.request_hash,
            goal_id=row.goal_id,
            response_json=row.response_json,
            created_at=row.created_at,
        )

    def lock_idempotency_commands(self, owner_id: str) -> None:
        """Serialize command-key checks for one owner on SQLite.

        A no-op write takes SQLite's transaction write lock before the
        idempotency lookup. A concurrent request therefore waits, then sees
        the first request's committed record instead of racing into a unique
        constraint after performing the command.
        """
        self._session.execute(
            update(LearnerProfileRow)
            .where(LearnerProfileRow.owner_id == owner_id)
            .values(owner_id=owner_id)
        )

    def add_idempotency(self, record: IdempotencyRecord) -> None:
        self._session.add(ProfilesGoalsIdempotencyRow(**record.__dict__))
        self._session.flush()


def _profile(row: LearnerProfileRow) -> LearnerProfile:
    return LearnerProfile(
        owner_id=row.owner_id,
        experience=row.experience,
        strengths=row.strengths,
        weaknesses=row.weaknesses,
        current_goal_id=row.current_goal_id,
        profile_revision=row.profile_revision,
        updated_at=row.updated_at,
    )


def _goal(row: GoalWorkspaceRow) -> GoalWorkspace:
    return GoalWorkspace(
        id=row.id,
        owner_id=row.owner_id,
        name=row.name,
        path=GoalPath(row.path),
        subject=row.subject,
        role=row.role,
        target_level=TargetLevel(row.target_level),
        target_capability=TargetCapability(row.target_capability),
        graph_version_id=row.graph_version_id,
        status=GoalStatus(row.status),
        resume_position=row.resume_position,
        last_accessed_at=row.last_accessed_at,
        row_version=row.row_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

"""Owner-scoped SQLAlchemy adapter for profile and goal persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from yuno.modules.data_lifecycle.models import (
    GoalWorkspaceBodyRow,
    LearnerProfileBodyRow,
    ProfilesGoalsIdempotencyBodyRow,
)
from yuno.modules.profiles_goals.domain import (
    GoalLifecycle,
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
from yuno.shared.domain.hashing import hash_payload
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
        pair = self._session.execute(
            select(LearnerProfileRow, LearnerProfileBodyRow)
            .join(
                LearnerProfileBodyRow,
                LearnerProfileBodyRow.owner_id == LearnerProfileRow.owner_id,
            )
            .where(LearnerProfileRow.owner_id == owner_id)
        ).one_or_none()
        return _profile(*pair) if pair is not None else None

    def create_profile(self, owner_id: str) -> LearnerProfile:
        body = LearnerProfileBodyRow(
            owner_id=owner_id, experience=None, strengths=None, weaknesses=None
        )
        row = LearnerProfileRow(
            owner_id=owner_id,
            body_hash=hash_payload(
                {"experience": None, "strengths": None, "weaknesses": None}
            ),
            updated_at=now_text(self._clock),
        )
        self._session.add(row)
        self._session.flush()
        self._session.add(body)
        self._session.flush()
        return _profile(row, body)

    def update_profile(
        self, owner_id: str, expected_revision: int, changes: Mapping[str, object]
    ) -> LearnerProfile | None:
        body_changes = {
            key: value
            for key, value in changes.items()
            if key in {"experience", "strengths", "weaknesses"}
        }
        values = {
            key: value for key, value in changes.items() if key not in body_changes
        }
        if body_changes:
            body = self._session.get(LearnerProfileBodyRow, owner_id)
            if body is None:
                return None
            for key, value in body_changes.items():
                setattr(body, key, value)
            values["body_hash"] = hash_payload(
                {
                    "experience": body.experience,
                    "strengths": body.strengths,
                    "weaknesses": body.weaknesses,
                }
            )
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
        return self.get_profile(owner_id)

    def list_goals(self, owner_id: str) -> Sequence[GoalWorkspace]:
        stmt = (
            owner_scoped_select(GoalWorkspaceRow, owner_id)
            .where(GoalWorkspaceRow.status != "tombstoned")
            .order_by(GoalWorkspaceRow.updated_at.desc())
        )
        rows = self._session.execute(
            stmt.join(
                GoalWorkspaceBodyRow,
                GoalWorkspaceBodyRow.goal_id == GoalWorkspaceRow.id,
            ).add_columns(GoalWorkspaceBodyRow)
        ).all()
        return tuple(_goal(row, body) for row, body in rows)

    def get_goal(self, owner_id: str, goal_id: str) -> GoalWorkspace | None:
        stmt = owner_scoped_select(GoalWorkspaceRow, owner_id).where(
            GoalWorkspaceRow.id == goal_id, GoalWorkspaceRow.status != "tombstoned"
        )
        pair = self._session.execute(
            stmt.join(
                GoalWorkspaceBodyRow,
                GoalWorkspaceBodyRow.goal_id == GoalWorkspaceRow.id,
            ).add_columns(GoalWorkspaceBodyRow)
        ).one_or_none()
        return _goal(*pair) if pair is not None else None

    def get_goal_for_lifecycle(
        self, owner_id: str, goal_id: str
    ) -> GoalLifecycle | None:
        row = self._session.scalars(
            owner_scoped_select(GoalWorkspaceRow, owner_id).where(
                GoalWorkspaceRow.id == goal_id
            )
        ).one_or_none()
        return (
            GoalLifecycle(row.id, row.owner_id, GoalStatus(row.status), row.row_version)
            if row
            else None
        )

    def create_goal(self, goal: GoalWorkspace) -> GoalWorkspace:
        row = GoalWorkspaceRow(
            id=goal.id,
            owner_id=goal.owner_id,
            body_hash=hash_payload(
                {
                    "name": goal.name,
                    "subject": goal.subject,
                    "role": goal.role,
                    "resume_position": goal.resume_position,
                }
            ),
            path=goal.path.value,
            target_level=goal.target_level.value,
            target_capability=goal.target_capability,
            graph_version_id=goal.graph_version_id,
            status=goal.status.value,
            last_accessed_at=goal.last_accessed_at,
            row_version=goal.row_version,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
        )
        self._session.add(row)
        self._session.flush()
        body = GoalWorkspaceBodyRow(
            goal_id=goal.id,
            owner_id=goal.owner_id,
            name=goal.name,
            subject=goal.subject,
            role=goal.role,
            resume_position=goal.resume_position,
        )
        self._session.add(body)
        self._session.flush()
        return _goal(row, body)

    def tombstone_goal(
        self, owner_id: str, goal_id: str, expected_version: int
    ) -> GoalLifecycle | None:
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
        body_changes = {
            key: value
            for key, value in changes.items()
            if key in {"name", "subject", "role", "resume_position"}
        }
        values = {
            key: value for key, value in changes.items() if key not in body_changes
        }
        if body_changes:
            body = self._session.get(GoalWorkspaceBodyRow, goal_id)
            if body is None:
                return None
            for key, value in body_changes.items():
                setattr(body, key, value)
            values["body_hash"] = hash_payload(
                {
                    "name": body.name,
                    "subject": body.subject,
                    "role": body.role,
                    "resume_position": body.resume_position,
                }
            )
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
        body = self._session.get(ProfilesGoalsIdempotencyBodyRow, row.id)
        if body is None:
            return None
        return IdempotencyRecord(
            id=row.id,
            owner_id=row.owner_id,
            operation=row.operation,
            idempotency_key=row.idempotency_key,
            request_hash=row.request_hash,
            goal_id=row.goal_id,
            response_json=body.response_json,
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
        values = record.__dict__.copy()
        response_json = values.pop("response_json")
        values["response_hash"] = hash_payload(response_json)
        self._session.add(ProfilesGoalsIdempotencyRow(**values))
        self._session.flush()
        self._session.add(
            ProfilesGoalsIdempotencyBodyRow(
                idempotency_id=record.id,
                owner_id=record.owner_id,
                response_json=response_json,
            )
        )
        self._session.flush()


def _profile(row: LearnerProfileRow, body: LearnerProfileBodyRow) -> LearnerProfile:
    return LearnerProfile(
        owner_id=row.owner_id,
        experience=body.experience,
        strengths=body.strengths,
        weaknesses=body.weaknesses,
        current_goal_id=row.current_goal_id,
        profile_revision=row.profile_revision,
        updated_at=row.updated_at,
    )


def _goal(row: GoalWorkspaceRow, body: GoalWorkspaceBodyRow) -> GoalWorkspace:
    return GoalWorkspace(
        id=row.id,
        owner_id=row.owner_id,
        name=body.name,
        path=GoalPath(row.path),
        subject=body.subject,
        role=body.role,
        target_level=TargetLevel(row.target_level),
        target_capability=TargetCapability(row.target_capability),
        graph_version_id=row.graph_version_id,
        status=GoalStatus(row.status),
        resume_position=body.resume_position,
        last_accessed_at=row.last_accessed_at,
        row_version=row.row_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

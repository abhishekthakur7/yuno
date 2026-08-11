"""Application services for global profiles and isolated goals."""

from __future__ import annotations

from collections.abc import Mapping

from yuno.modules.audit.domain import AuditEvent
from yuno.modules.profiles_goals.domain import (
    GoalNavigationEvent,
    GoalPath,
    GoalStatus,
    GoalWorkspace,
    LearnerProfile,
    RecommendationDismissal,
    ResumeDestination,
    TargetCapability,
    TargetLevel,
    validate_goal_fields,
    validate_resume_destination,
)
from yuno.modules.profiles_goals.ports import ProfilesGoalsUnitOfWork
from yuno.shared.domain.clock import Clock, SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
    PreconditionFailedError,
    UnavailableError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def ensure_profile(uow: ProfilesGoalsUnitOfWork, owner_id: str) -> LearnerProfile:
    profile = uow.profiles_goals.get_profile(owner_id)
    if profile is not None:
        return profile
    return uow.profiles_goals.create_profile(owner_id)


def patch_profile(
    uow: ProfilesGoalsUnitOfWork,
    owner_id: str,
    expected_revision: int,
    changes: Mapping[str, object],
    *,
    clock: Clock | None = None,
) -> LearnerProfile:
    before = _require_profile(uow, owner_id)
    if before.profile_revision != expected_revision:
        raise PreconditionFailedError("The profile has changed; reload it and retry.")
    updated = uow.profiles_goals.update_profile(owner_id, expected_revision, changes)
    if updated is None:
        raise PreconditionFailedError("The profile has changed; reload it and retry.")
    _audit(
        uow,
        owner_id,
        None,
        "learner_profile",
        owner_id,
        "updated",
        before,
        updated,
        clock,
    )
    return updated


def create_goal(
    uow: ProfilesGoalsUnitOfWork,
    owner_id: str,
    *,
    name: str,
    path: GoalPath,
    subject: str | None,
    role: str | None,
    target_level: TargetLevel,
    target_capability: TargetCapability,
    graph_version_id: str,
    approved_graph_exists: bool,
    clock: Clock | None = None,
) -> GoalWorkspace:
    validate_goal_fields(
        name=name,
        path=path,
        subject=subject,
        role=role,
    )
    if not approved_graph_exists:
        raise NotFoundError("The approved canonical graph version was not found.")
    timestamp = now_text(clock or SystemClock())
    goal = GoalWorkspace(
        id=new_id(),
        owner_id=owner_id,
        name=name.strip(),
        path=path,
        subject=subject.strip() if subject else None,
        role=role.strip() if role else None,
        target_level=target_level,
        target_capability=target_capability,
        graph_version_id=graph_version_id,
        status=GoalStatus.ACTIVE,
        resume_position=None,
        last_accessed_at=timestamp,
        row_version=1,
        created_at=timestamp,
        updated_at=timestamp,
    )
    created = uow.profiles_goals.create_goal(goal)
    profile = _require_profile(uow, owner_id)
    if profile.current_goal_id is None:
        selected = uow.profiles_goals.update_profile(
            owner_id, profile.profile_revision, {"current_goal_id": created.id}
        )
        if selected is None:
            raise PreconditionFailedError(
                "The profile has changed; reload it and retry."
            )
        _audit(
            uow,
            owner_id,
            created.id,
            "learner_profile",
            owner_id,
            "current_goal_selected",
            profile,
            selected,
            clock,
        )
    _audit(
        uow,
        owner_id,
        created.id,
        "goal_workspace",
        created.id,
        "created",
        None,
        created,
        clock,
    )
    return created


def patch_goal(
    uow: ProfilesGoalsUnitOfWork,
    owner_id: str,
    goal_id: str,
    expected_version: int,
    changes: Mapping[str, object],
    *,
    set_current: bool = False,
    resume_destination: ResumeDestination | None = None,
    dismiss_recommendation_key: str | None = None,
    published_topic_ids: frozenset[str],
    clock: Clock | None = None,
) -> GoalWorkspace:
    before = _require_goal(uow, owner_id, goal_id)
    if before.row_version != expected_version:
        raise PreconditionFailedError("The goal has changed; reload it and retry.")
    if before.status is GoalStatus.ARCHIVED:
        raise ConflictError("An archived goal cannot be changed or selected.")
    for required_field in ("name", "target_level", "target_capability"):
        if required_field in changes and changes[required_field] is None:
            raise DomainValidationError(
                f"Goal field '{required_field}' cannot be null."
            )

    candidate_name = str(changes.get("name", before.name))
    candidate_subject = changes.get("subject", before.subject)
    candidate_role = changes.get("role", before.role)
    candidate_capability = TargetCapability(
        str(changes.get("target_capability", before.target_capability.value))
    )
    validate_goal_fields(
        name=candidate_name,
        path=before.path,
        subject=str(candidate_subject) if candidate_subject is not None else None,
        role=str(candidate_role) if candidate_role is not None else None,
    )
    timestamp = now_text(clock or SystemClock())
    persistence_changes = dict(changes)
    if "name" in persistence_changes:
        persistence_changes["name"] = candidate_name.strip()
    if "subject" in persistence_changes and candidate_subject is not None:
        persistence_changes["subject"] = str(candidate_subject).strip()
    if "role" in persistence_changes and candidate_role is not None:
        persistence_changes["role"] = str(candidate_role).strip()
    if "target_capability" in persistence_changes:
        persistence_changes["target_capability"] = candidate_capability.value
    if "target_level" in persistence_changes:
        persistence_changes["target_level"] = TargetLevel(
            str(persistence_changes["target_level"])
        ).value
    if "resume_position" in persistence_changes:
        position = persistence_changes["resume_position"]
        if position is not None:
            stable_id = str(position).strip()
            if not stable_id:
                raise DomainValidationError("Resume position must not be blank.")
            if stable_id not in published_topic_ids:
                raise DomainValidationError(
                    "Resume position must identify a topic in the goal's approved canonical graph."
                )
            persistence_changes["resume_position"] = stable_id
        persistence_changes["last_accessed_at"] = timestamp
    elif set_current:
        persistence_changes["last_accessed_at"] = timestamp

    destination: ResumeDestination | None = None
    if "resume_position" in changes:
        destination = resume_destination or (
            ResumeDestination.LEARN_ROADMAP
            if before.path is GoalPath.LEARN
            else ResumeDestination.INTERVIEW_HUB
        )
        validate_resume_destination(before.path, destination)

    if persistence_changes:
        updated = uow.profiles_goals.update_goal(
            owner_id, goal_id, expected_version, persistence_changes
        )
        if updated is None:
            raise PreconditionFailedError("The goal has changed; reload it and retry.")
    else:
        updated = before
    if "resume_position" in changes:
        assert destination is not None
        uow.profiles_goals.append_navigation(
            GoalNavigationEvent(
                id=new_id(),
                owner_id=owner_id,
                goal_id=goal_id,
                position=persistence_changes["resume_position"],
                destination=destination,
                occurred_at=timestamp,
            )
        )
    if dismiss_recommendation_key is not None:
        if not dismiss_recommendation_key.strip():
            raise ConflictError("Recommendation key must not be blank.")
        dismissal = RecommendationDismissal(
            id=new_id(),
            owner_id=owner_id,
            goal_id=goal_id,
            recommendation_key=dismiss_recommendation_key.strip(),
            dismissed_at=timestamp,
        )
        if uow.profiles_goals.add_dismissal(dismissal):
            _audit(
                uow,
                owner_id,
                goal_id,
                "recommendation_dismissal",
                dismissal.recommendation_key,
                "created",
                None,
                dismissal,
                clock,
            )
    if set_current:
        profile = _require_profile(uow, owner_id)
        switched = uow.profiles_goals.update_profile(
            owner_id, profile.profile_revision, {"current_goal_id": goal_id}
        )
        if switched is None:
            raise PreconditionFailedError(
                "The profile has changed; reload it and retry."
            )
        _audit(
            uow,
            owner_id,
            goal_id,
            "learner_profile",
            owner_id,
            "current_goal_selected",
            profile,
            switched,
            clock,
        )
    if persistence_changes:
        _audit(
            uow,
            owner_id,
            goal_id,
            "goal_workspace",
            goal_id,
            "updated",
            before,
            updated,
            clock,
        )
    return updated


def archive_goal(
    uow: ProfilesGoalsUnitOfWork,
    owner_id: str,
    goal_id: str,
    expected_version: int,
    *,
    clock: Clock | None = None,
) -> GoalWorkspace:
    before = _require_goal(uow, owner_id, goal_id)
    if before.row_version != expected_version:
        raise PreconditionFailedError("The goal has changed; reload it and retry.")
    if before.status is GoalStatus.ARCHIVED:
        return before
    updated = uow.profiles_goals.update_goal(
        owner_id, goal_id, expected_version, {"status": GoalStatus.ARCHIVED.value}
    )
    if updated is None:
        raise PreconditionFailedError("The goal has changed; reload it and retry.")
    profile = _require_profile(uow, owner_id)
    if profile.current_goal_id == goal_id:
        cleared = uow.profiles_goals.update_profile(
            owner_id, profile.profile_revision, {"current_goal_id": None}
        )
        if cleared is None:
            raise PreconditionFailedError(
                "The profile has changed; reload it and retry."
            )
        _audit(
            uow,
            owner_id,
            goal_id,
            "learner_profile",
            owner_id,
            "current_goal_cleared",
            profile,
            cleared,
            clock,
        )
    _audit(
        uow,
        owner_id,
        goal_id,
        "goal_workspace",
        goal_id,
        "archived",
        before,
        updated,
        clock,
    )
    return updated


def _require_profile(uow: ProfilesGoalsUnitOfWork, owner_id: str) -> LearnerProfile:
    profile = uow.profiles_goals.get_profile(owner_id)
    if profile is None:
        raise UnavailableError(
            "The learner profile is unavailable; retry after recovery."
        )
    return profile


def _require_goal(
    uow: ProfilesGoalsUnitOfWork, owner_id: str, goal_id: str
) -> GoalWorkspace:
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal '{goal_id}' was not found.")
    return goal


def _audit(
    uow: ProfilesGoalsUnitOfWork,
    owner_id: str,
    goal_id: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    before: object | None,
    after: object,
    clock: Clock | None,
) -> None:
    uow.audit.append(
        AuditEvent(
            id=new_id(),
            owner_id=owner_id,
            goal_id=goal_id,
            actor_role="learner",
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_hash=hash_payload(before) if before is not None else None,
            after_hash=hash_payload(after),
            reason=None,
            request_id=None,
            correlation_id=None,
            occurred_at=now_text(clock or SystemClock()),
        )
    )

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    Topic,
    TopicIdentity,
)
from yuno.modules.profiles_goals.domain import GoalPath, TargetCapability, TargetLevel
from yuno.modules.profiles_goals.service import create_goal, patch_goal
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id


def _seed_approved_graph(uow_factory: UnitOfWorkFactory, owner_id: str) -> str:
    graph_id = new_id()
    timestamp = now_text(SystemClock())
    with uow_factory() as uow:
        uow.canonical.create_topic_identity(
            TopicIdentity(
                stable_id="queues",
                stable_slug="queues",
                created_at=timestamp,
                retired_at=None,
            )
        )
        uow.canonical.create_version(
            CanonicalGraphVersion(
                id=graph_id,
                version_label="profiles-goals-v1",
                manifest_version="v1",
                manifest_hash=new_id(),
                status=CanonicalVersionStatus.PUBLISHED,
                creator_owner_id=owner_id,
                created_at=timestamp,
                published_at=timestamp,
                supersedes_version_id=None,
            )
        )
        uow.canonical.add_topic(
            Topic(
                graph_version_id=graph_id,
                stable_id="queues",
                title="Queues",
                subject="dsa",
                scope_tags=("fixture",),
                level_tag="Senior",
                target_capability="implement",
                recommended_layer="Essential",
                checkpoint_start=0,
                checkpoint_end=1,
            )
        )
        uow.canonical.record_approval(
            EditorialApproval(
                id=new_id(),
                graph_version_id=graph_id,
                approver_owner_id=owner_id,
                approver_role="designated_editorial_approver",
                basis_ref="test",
                approved_at=timestamp,
            )
        )
        uow.commit()
    return graph_id


def _owner_id(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        profile = uow.profiles_goals.get_profile(owner.id)
    assert profile is not None, "startup must provision exactly one global profile"
    return owner.id


def test_two_goal_navigation_and_dismissal_history_is_isolated(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner_id(uow_factory)
    graph_id = _seed_approved_graph(uow_factory, owner_id)
    with uow_factory() as uow:
        goal_a = create_goal(
            uow,
            owner_id,
            name="Learn DSA",
            path=GoalPath.LEARN,
            subject="DSA",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.IMPLEMENT,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        goal_b = create_goal(
            uow,
            owner_id,
            name="Backend interview",
            path=GoalPath.INTERVIEW_PREP,
            subject=None,
            role="Backend Engineer",
            target_level=TargetLevel.STAFF,
            target_capability=TargetCapability.DEFEND,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        updated_a = patch_goal(
            uow,
            owner_id,
            goal_a.id,
            goal_a.row_version,
            {"resume_position": "queues"},
            resume_destination="/app/topic-studio",
            dismiss_recommendation_key="review-queues-v1",
            published_topic_ids=frozenset({"queues"}),
        )
        patch_goal(
            uow,
            owner_id,
            goal_a.id,
            updated_a.row_version,
            {},
            dismiss_recommendation_key="review-queues-v1",
            published_topic_ids=frozenset(),
        )
        uow.commit()

    with uow_factory() as uow:
        a_navigation = uow.profiles_goals.list_navigation(owner_id, goal_a.id)
        b_navigation = uow.profiles_goals.list_navigation(owner_id, goal_b.id)
        a_dismissals = uow.profiles_goals.list_dismissals(owner_id, goal_a.id)
        b_dismissals = uow.profiles_goals.list_dismissals(owner_id, goal_b.id)
        stored_b = uow.profiles_goals.get_goal(owner_id, goal_b.id)
        dismissal_audits = [
            event
            for event in uow.audit.list_for_owner(owner_id)
            if event.entity_type == "recommendation_dismissal"
        ]

    assert [event.position for event in a_navigation] == ["queues"]
    assert b_navigation == ()
    assert [item.recommendation_key for item in a_dismissals] == ["review-queues-v1"]
    assert b_dismissals == ()
    assert stored_b is not None and stored_b.resume_position is None
    assert len(dismissal_audits) == 1


def test_switching_away_and_back_preserves_the_saved_resume_destination(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner_id(uow_factory)
    graph_id = _seed_approved_graph(uow_factory, owner_id)
    with uow_factory() as uow:
        goal_a = create_goal(
            uow,
            owner_id,
            name="Saved Learn position",
            path=GoalPath.LEARN,
            subject="Distributed systems",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.DIAGNOSE,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        goal_b = create_goal(
            uow,
            owner_id,
            name="Interview workspace",
            path=GoalPath.INTERVIEW_PREP,
            subject=None,
            role="Backend Engineer",
            target_level=TargetLevel.STAFF,
            target_capability=TargetCapability.DEFEND,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        saved_a = patch_goal(
            uow,
            owner_id,
            goal_a.id,
            goal_a.row_version,
            {"resume_position": "failure-boundary"},
            resume_destination="/app/topic-studio",
            published_topic_ids=frozenset({"failure-boundary"}),
        )
        patch_goal(
            uow,
            owner_id,
            goal_b.id,
            goal_b.row_version,
            {},
            set_current=True,
            published_topic_ids=frozenset(),
        )
        patch_goal(
            uow,
            owner_id,
            goal_a.id,
            saved_a.row_version,
            {},
            set_current=True,
            published_topic_ids=frozenset(),
        )
        uow.commit()

    with uow_factory() as uow:
        navigation = uow.profiles_goals.list_navigation(owner_id, goal_a.id)
        profile = uow.profiles_goals.get_profile(owner_id)
        stored_a = uow.profiles_goals.get_goal(owner_id, goal_a.id)
        stored_b = uow.profiles_goals.get_goal(owner_id, goal_b.id)

    assert [(event.position, event.destination) for event in navigation] == [
        ("failure-boundary", "/app/topic-studio")
    ]
    assert profile is not None and profile.current_goal_id == goal_a.id
    assert stored_a is not None and stored_a.row_version == 3
    assert stored_b is not None and stored_b.row_version == 2
    assert stored_b.last_accessed_at is not None


def test_profile_goal_api_resume_archive_and_versions(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner_id(uow_factory)
    graph_id = _seed_approved_graph(uow_factory, owner_id)
    headers = {"Idempotency-Key": "create-api-goal"}
    created = client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "name": " API Learn ",
            "path": "learn",
            "subject": " DSA ",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": graph_id,
        },
    )
    assert created.status_code == 201, created.text
    goal = created.json()
    assert goal["name"] == "API Learn" and goal["subject"] == "DSA"
    replay = client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "name": " API Learn ",
            "path": "learn",
            "subject": " DSA ",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": graph_id,
        },
    )
    assert replay.status_code == 201 and replay.json()["id"] == goal["id"]
    conflict = client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "name": "Different",
            "path": "learn",
            "subject": "DSA",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": graph_id,
        },
    )
    assert conflict.status_code == 409

    updated = client.patch(
        f"/api/v1/goals/{goal['id']}",
        headers={"If-Match": "1"},
        json={
            "resume_position": "queues",
            "resume_destination": "/app/topic-studio",
            "dismiss_recommendation_key": "next-queues-v1",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["dismissed_recommendation_keys"] == ["next-queues-v1"]
    assert updated.json()["row_version"] == 2
    replay_after_mutation = client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "name": " API Learn ",
            "path": "learn",
            "subject": " DSA ",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": graph_id,
        },
    )
    assert replay_after_mutation.status_code == 201
    assert replay_after_mutation.json()["row_version"] == 1
    assert replay_after_mutation.json()["dismissed_recommendation_keys"] == []

    stale = client.patch(
        f"/api/v1/goals/{goal['id']}", headers={"If-Match": "1"}, json={"name": "stale"}
    )
    assert stale.status_code == 412

    archived = client.post(
        f"/api/v1/goals/{goal['id']}/archive",
        headers={"If-Match": "2", "Idempotency-Key": "archive-api-goal"},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    archive_replay = client.post(
        f"/api/v1/goals/{goal['id']}/archive",
        headers={"If-Match": "2", "Idempotency-Key": "archive-api-goal"},
    )
    assert (
        archive_replay.status_code == 200 and archive_replay.json()["row_version"] == 3
    )
    archive_conflict = client.post(
        f"/api/v1/goals/{goal['id']}/archive",
        headers={"If-Match": "3", "Idempotency-Key": "archive-api-goal"},
    )
    assert archive_conflict.status_code == 409
    assert client.get("/api/v1/profile").json()["current_goal_id"] is None

    profile = client.get("/api/v1/profile").json()
    patched = client.patch(
        "/api/v1/profile",
        headers={"If-Match": str(profile["profile_revision"])},
        json={"experience": "Production systems"},
    )
    assert patched.status_code == 200
    assert (
        client.patch(
            "/api/v1/profile",
            headers={"If-Match": str(profile["profile_revision"])},
            json={"strengths": "stale"},
        ).status_code
        == 412
    )


def test_goal_create_rejects_unapproved_graph_and_irrelevant_role(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner_id(uow_factory)
    unapproved_id = new_id()
    timestamp = now_text(SystemClock())
    with uow_factory() as uow:
        uow.canonical.create_version(
            CanonicalGraphVersion(
                id=unapproved_id,
                version_label="draft",
                manifest_version="v1",
                manifest_hash=new_id(),
                status=CanonicalVersionStatus.PENDING_APPROVAL,
                creator_owner_id=owner_id,
                created_at=timestamp,
                published_at=None,
                supersedes_version_id=None,
            )
        )
        uow.commit()
    response = client.post(
        "/api/v1/goals",
        headers={"Idempotency-Key": "bad-graph"},
        json={
            "name": "Bad",
            "path": "learn",
            "subject": "DSA",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": unapproved_id,
        },
    )
    assert response.status_code == 404
    approved_id = _seed_approved_graph(uow_factory, owner_id)
    irrelevant = client.post(
        "/api/v1/goals",
        headers={"Idempotency-Key": "bad-role"},
        json={
            "name": "Bad",
            "path": "learn",
            "subject": "DSA",
            "role": "Engineer",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": approved_id,
        },
    )
    assert irrelevant.status_code == 422


def test_navigation_and_dismissal_rows_are_database_immutable(
    client: TestClient, uow_factory: UnitOfWorkFactory, engine
) -> None:
    owner_id = _owner_id(uow_factory)
    graph_id = _seed_approved_graph(uow_factory, owner_id)
    with uow_factory() as uow:
        goal = create_goal(
            uow,
            owner_id,
            name="Immutable history",
            path=GoalPath.LEARN,
            subject="DSA",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.IMPLEMENT,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        patch_goal(
            uow,
            owner_id,
            goal.id,
            1,
            {"resume_position": "a"},
            resume_destination="/app/topic-studio",
            dismiss_recommendation_key="rec-a",
            published_topic_ids=frozenset({"a"}),
        )
        uow.commit()
    with engine.begin() as connection:
        for table in ("goal_navigation_events", "recommendation_dismissals"):
            try:
                connection.execute(text(f"UPDATE {table} SET owner_id = owner_id"))
            except IntegrityError:
                pass
            else:
                raise AssertionError(f"{table} UPDATE should be rejected")


def test_resume_requires_a_compatible_route_and_pinned_graph_topic(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner_id(uow_factory)
    graph_id = _seed_approved_graph(uow_factory, owner_id)
    created = client.post(
        "/api/v1/goals",
        headers={"Idempotency-Key": "resume-validation"},
        json={
            "name": "Validated resume",
            "path": "learn",
            "subject": "DSA",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": graph_id,
        },
    ).json()

    wrong_route = client.patch(
        f"/api/v1/goals/{created['id']}",
        headers={"If-Match": "1"},
        json={
            "resume_position": "queues",
            "resume_destination": "/app/interview-hub",
        },
    )
    assert wrong_route.status_code == 422

    unknown_topic = client.patch(
        f"/api/v1/goals/{created['id']}",
        headers={"If-Match": "1"},
        json={
            "resume_position": "not-in-pinned-graph",
            "resume_destination": "/app/topic-studio",
        },
    )
    assert unknown_topic.status_code == 422


def test_missing_profile_is_unavailable(
    client: TestClient, uow_factory: UnitOfWorkFactory, engine
) -> None:
    owner_id = _owner_id(uow_factory)
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM learner_profiles WHERE owner_id = :owner_id"),
            {"owner_id": owner_id},
        )

    assert client.get("/api/v1/profile").status_code == 503
    assert client.get("/api/v1/goals").status_code == 503


def test_concurrent_create_with_same_idempotency_key_replays_one_result(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner_id(uow_factory)
    graph_id = _seed_approved_graph(uow_factory, owner_id)
    payload = {
        "name": "Exactly once",
        "path": "learn",
        "subject": "DSA",
        "target_level": "Senior",
        "target_capability": "implement",
        "graph_version_id": graph_id,
    }
    barrier = Barrier(2)

    def create() -> tuple[int, dict[str, object]]:
        barrier.wait()
        response = client.post(
            "/api/v1/goals",
            headers={"Idempotency-Key": "concurrent-create"},
            json=payload,
        )
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: create(), range(2)))

    assert [status_code for status_code, _body in results] == [201, 201]
    assert results[0][1]["id"] == results[1][1]["id"]
    with uow_factory() as uow:
        matching = [
            goal
            for goal in uow.profiles_goals.list_goals(owner_id)
            if goal.name == "Exactly once"
        ]
    assert len(matching) == 1

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    RelationType,
    Topic,
    TopicIdentity,
    TopicRelation,
)
from yuno.modules.profiles_goals.domain import GoalPath, TargetCapability, TargetLevel
from yuno.modules.profiles_goals.service import create_goal
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id


def _setup(uow_factory: UnitOfWorkFactory) -> tuple[str, str]:
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        now = now_text(SystemClock())
        graph_id = new_id()
        for stable_id in ("topic-z", "topic-a", "topic-m"):
            uow.canonical.create_topic_identity(
                TopicIdentity(stable_id, stable_id, now, None)
            )
        uow.canonical.create_version(
            CanonicalGraphVersion(
                graph_id,
                f"roadmap-{graph_id}",
                "v1",
                new_id(),
                CanonicalVersionStatus.PUBLISHED,
                owner.id,
                now,
                now,
                None,
            )
        )
        for stable_id in ("topic-z", "topic-a", "topic-m"):
            uow.canonical.add_topic(
                Topic(
                    graph_id,
                    stable_id,
                    stable_id,
                    "java",
                    ("fixture",),
                    "Senior",
                    "implement",
                    "Implementation",
                    0,
                    1,
                )
            )
        uow.canonical.add_relation(
            TopicRelation(
                new_id(),
                graph_id,
                "topic-a",
                "topic-z",
                RelationType.PREREQUISITE,
                None,
            )
        )
        uow.canonical.record_approval(
            EditorialApproval(
                new_id(),
                graph_id,
                owner.id,
                "designated_editorial_approver",
                "test",
                now,
            )
        )
        goal = create_goal(
            uow,
            owner.id,
            name="Roadmap",
            path=GoalPath.LEARN,
            subject="Java",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.IMPLEMENT,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        uow.commit()
    return owner.id, goal.id


def test_reads_are_pure_and_explicit_mutations_are_append_only(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, goal_id = _setup(uow_factory)
    first = client.get(f"/api/v1/goals/{goal_id}/roadmap")
    second = client.get(f"/api/v1/goals/{goal_id}/roadmap")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert [item["stable_id"] for item in first.json()["topics"]] == [
        "topic-a",
        "topic-m",
        "topic-z",
    ]
    with uow_factory() as uow:
        assert uow.roadmap.get_overlay(owner_id, goal_id) is None
        assert uow.roadmap.list_overlay_entries(owner_id, goal_id) == ()

    saved = client.post(
        f"/api/v1/goals/{goal_id}/depth-overrides",
        headers={"Idempotency-Key": "depth-1"},
        json={"topic_stable_id": "topic-a", "depth": "Internals"},
    )
    assert saved.status_code == 200, saved.text
    topic = saved.json()["projection"]["topics"][0]
    assert topic["recommended_depth"] == "Implementation"
    assert topic["depth_override"] == "Internals"
    replay = client.post(
        f"/api/v1/goals/{goal_id}/depth-overrides",
        headers={"Idempotency-Key": "depth-1"},
        json={"topic_stable_id": "topic-a", "depth": "Internals"},
    )
    assert replay.status_code == 200
    assert replay.json() == saved.json()

    invalid = client.post(
        f"/api/v1/goals/{goal_id}/order-constraints",
        headers={"Idempotency-Key": "order-1"},
        json={"before_topic_id": "topic-z", "after_topic_id": "topic-a"},
    )
    assert invalid.status_code == 409
    assert invalid.json()["code"] == "invalid_order_constraint"
    with uow_factory() as uow:
        assert len(uow.roadmap.list_overlay_entries(owner_id, goal_id)) == 1


def test_database_rejects_overlay_entry_update(
    client: TestClient, uow_factory: UnitOfWorkFactory, engine: Engine
) -> None:
    owner_id, goal_id = _setup(uow_factory)
    response = client.post(
        f"/api/v1/goals/{goal_id}/skip-decisions",
        headers={"Idempotency-Key": "skip-1"},
        json={"topic_stable_id": "topic-a", "skipped": True},
    )
    assert response.status_code == 200
    with uow_factory() as uow:
        entry = uow.roadmap.list_overlay_entries(owner_id, goal_id)[0]
    with (
        engine.begin() as connection,
        pytest.raises(IntegrityError, match="append-only"),
    ):
        connection.execute(
            text("UPDATE overlay_entries SET content_hash='changed' WHERE id=:id"),
            {"id": entry.id},
        )


def test_reversing_learner_order_supersedes_the_prior_constraint(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, goal_id = _setup(uow_factory)
    first = client.post(
        f"/api/v1/goals/{goal_id}/order-constraints",
        headers={"Idempotency-Key": "order-forward"},
        json={"before_topic_id": "topic-m", "after_topic_id": "topic-a"},
    )
    assert first.status_code == 200, first.text
    assert [topic["stable_id"] for topic in first.json()["projection"]["topics"]] == [
        "topic-m",
        "topic-a",
        "topic-z",
    ]

    reversed_order = client.post(
        f"/api/v1/goals/{goal_id}/order-constraints",
        headers={"Idempotency-Key": "order-reversed"},
        json={"before_topic_id": "topic-a", "after_topic_id": "topic-m"},
    )
    assert reversed_order.status_code == 200, reversed_order.text
    assert [
        topic["stable_id"] for topic in reversed_order.json()["projection"]["topics"]
    ] == ["topic-a", "topic-m", "topic-z"]
    with uow_factory() as uow:
        entries = uow.roadmap.list_overlay_entries(owner_id, goal_id)
    assert len(entries) == 2
    assert entries[1].supersedes_entry_id == entries[0].id

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    Topic,
    TopicIdentity,
)
from yuno.modules.profiles_goals.domain import GoalPath, TargetCapability, TargetLevel
from yuno.modules.profiles_goals.service import create_goal
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id


def _graph(uow, owner_id: str, label: str, *, identity_exists: bool) -> str:
    now = now_text(SystemClock())
    graph_id = new_id()
    if not identity_exists:
        uow.canonical.create_topic_identity(
            TopicIdentity("topic-a", "topic-a", now, None)
        )
    uow.canonical.create_version(
        CanonicalGraphVersion(
            graph_id,
            label,
            "v1",
            new_id(),
            CanonicalVersionStatus.PUBLISHED,
            owner_id,
            now,
            now,
            None,
        )
    )
    uow.canonical.add_topic(
        Topic(
            graph_id,
            "topic-a",
            "Topic A",
            "java",
            ("fixture",),
            "Senior",
            "implement",
            "Implementation",
            0,
            1,
        )
    )
    uow.canonical.record_approval(
        EditorialApproval(
            new_id(), graph_id, owner_id, "designated_editorial_approver", "test", now
        )
    )
    return graph_id


def _setup(uow_factory: UnitOfWorkFactory) -> tuple[str, str, str]:
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        graph_id = _graph(uow, owner.id, "proposal-v1", identity_exists=False)
        goal = create_goal(
            uow,
            owner.id,
            name="Proposal goal",
            path=GoalPath.LEARN,
            subject="Java",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.IMPLEMENT,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        uow.commit()
    return owner.id, goal.id, graph_id


def _create(
    client: TestClient,
    goal_id: str,
    graph_id: str,
    *,
    key: str,
    proposal_type: str = "recommendation",
    payload: dict[str, object] | None = None,
):
    return client.post(
        f"/api/v1/goals/{goal_id}/overlay-proposals",
        headers={"Idempotency-Key": key},
        json={
            "generated_against_graph_version_id": graph_id,
            "topic_stable_id": "topic-a",
            "proposal_type": proposal_type,
            "payload": payload or {"message": "Try a diagnostic exercise."},
        },
    )


def test_create_is_annotation_only_and_pending_hash_is_deduplicated(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, goal_id, graph_id = _setup(uow_factory)
    first = _create(client, goal_id, graph_id, key="proposal-1")
    assert first.status_code == 201, first.text
    assert first.json()["state"] == "awaiting-learner-decision"
    duplicate = _create(client, goal_id, graph_id, key="proposal-2")
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["id"] == first.json()["id"]
    assert duplicate.json()["deduplicated"] is True

    roadmap = client.get(f"/api/v1/goals/{goal_id}/roadmap")
    assert (
        roadmap.json()["topics"][0]["pending_proposals"][0]["id"] == first.json()["id"]
    )
    with uow_factory() as uow:
        assert len(uow.roadmap.list_proposals(owner_id, goal_id)) == 1
        assert uow.roadmap.list_overlay_entries(owner_id, goal_id) == ()
        proposal_audits = [
            event
            for event in uow.audit.list_for_owner(owner_id)
            if event.entity_type == "overlay_proposal"
        ]
        assert [event.action for event in proposal_audits] == ["created"]


def test_pending_cap_rejects_next_proposal_with_visible_feedback(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    _owner_id, goal_id, graph_id = _setup(uow_factory)
    for index in range(25):
        created = _create(
            client,
            goal_id,
            graph_id,
            key=f"cap-{index}",
            payload={"message": f"Recommendation {index}."},
        )
        assert created.status_code == 201
    capped = _create(
        client,
        goal_id,
        graph_id,
        key="cap-overflow",
        payload={"message": "Different recommendation."},
    )
    assert capped.status_code == 409
    assert capped.json()["code"] == "pending-cap-exceeded"
    assert capped.json()["recovery_action"] == "Review existing pending proposals."


def test_stale_accept_persists_rejection_history_and_applies_nothing(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, goal_id, graph_v1 = _setup(uow_factory)
    proposal = _create(client, goal_id, graph_v1, key="stale-create").json()
    with uow_factory() as uow:
        graph_v2 = _graph(uow, owner_id, "proposal-v2", identity_exists=True)
        goal = uow.profiles_goals.get_goal(owner_id, goal_id)
        assert goal is not None
        assert uow.profiles_goals.update_goal(
            owner_id, goal_id, goal.row_version, {"graph_version_id": graph_v2}
        )
        uow.commit()

    stale = client.post(
        f"/api/v1/overlay-proposals/{proposal['id']}/decision",
        headers={"Idempotency-Key": "stale-accept"},
        json={"decision": "accept", "reason": "Looks useful"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "proposal_stale"
    assert graph_v1 in stale.json()["message"] and graph_v2 in stale.json()["message"]
    listed = client.get(f"/api/v1/goals/{goal_id}/overlay-proposals").json()
    assert listed[0]["state"] == "rejected-stale"
    assert listed[0]["decisions"][0]["decision"] == "accept"
    replay = client.post(
        f"/api/v1/overlay-proposals/{proposal['id']}/decision",
        headers={"Idempotency-Key": "stale-accept"},
        json={"decision": "accept", "reason": "Looks useful"},
    )
    assert replay.status_code == 409
    assert replay.json()["code"] == "proposal_stale"
    assert replay.json()["message"] == stale.json()["message"]
    assert (
        len(
            client.get(f"/api/v1/goals/{goal_id}/overlay-proposals").json()[0][
                "decisions"
            ]
        )
        == 1
    )
    with uow_factory() as uow:
        assert uow.roadmap.list_overlay_entries(owner_id, goal_id) == ()
        proposal_audits = [
            event
            for event in uow.audit.list_for_owner(owner_id)
            if event.entity_type == "overlay_proposal"
        ]
        assert {event.action for event in proposal_audits} == {
            "created",
            "rejected_stale",
        }


def test_bridge_requires_explanation_and_only_add_applies_overlay(
    client: TestClient, uow_factory: UnitOfWorkFactory, engine: Engine
) -> None:
    owner_id, goal_id, graph_id = _setup(uow_factory)
    invalid = _create(
        client,
        goal_id,
        graph_id,
        key="bridge-invalid",
        proposal_type="bridge",
        payload={
            "why": "",
            "relationship": "prerequisite",
            "proposed_placement": "before",
        },
    )
    assert invalid.status_code == 422
    bridge = _create(
        client,
        goal_id,
        graph_id,
        key="bridge-valid",
        proposal_type="bridge",
        payload={
            "why": "This fills a prerequisite gap.",
            "relationship": "prerequisite",
            "proposed_placement": {"before_topic_id": "topic-a"},
        },
    ).json()
    postponed = client.post(
        f"/api/v1/bridges/{bridge['id']}/decision",
        headers={"Idempotency-Key": "bridge-postpone"},
        json={"decision": "postpone", "reason": "Later"},
    )
    assert postponed.status_code == 200
    with uow_factory() as uow:
        assert uow.roadmap.list_overlay_entries(owner_id, goal_id) == ()
    added = client.post(
        f"/api/v1/bridges/{bridge['id']}/decision",
        headers={"Idempotency-Key": "bridge-add"},
        json={"decision": "add", "reason": "Ready"},
    )
    assert added.status_code == 200, added.text
    assert [item["decision"] for item in added.json()["decisions"]] == [
        "postpone",
        "add",
    ]
    with uow_factory() as uow:
        entries = uow.roadmap.list_overlay_entries(owner_id, goal_id)
        assert len(entries) == 1 and entries[0].entry_type.value == "bridge"
    decision_id = added.json()["decisions"][0]["id"]
    with (
        engine.begin() as connection,
        pytest.raises(IntegrityError, match="append-only"),
    ):
        connection.execute(
            text(
                "UPDATE overlay_proposal_decision_bodies SET reason='changed' WHERE decision_id=:id"
            ),
            {"id": decision_id},
        )


def test_unknown_owner_cannot_read_another_owners_proposal(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    _owner_id, goal_id, graph_id = _setup(uow_factory)
    proposal_id = _create(client, goal_id, graph_id, key="isolation-create").json()[
        "id"
    ]
    with uow_factory() as uow:
        assert uow.roadmap.get_proposal("owner-b", proposal_id) is None

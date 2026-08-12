from __future__ import annotations

import json
from urllib.parse import quote

from fastapi.testclient import TestClient

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    ContentRevision,
    EditorialApproval,
    Topic,
    TopicIdentity,
)
from yuno.modules.learning_content.domain import TopicLayer
from yuno.modules.profiles_goals.domain import GoalPath, TargetCapability, TargetLevel
from yuno.modules.profiles_goals.service import create_goal
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id


def _inline(value: str) -> str:
    return f"inline:{quote(value, safe='')}"


def _seed(uow_factory: UnitOfWorkFactory) -> tuple[str, str, str]:
    timestamp = now_text(SystemClock())
    graph_id = new_id()
    topic_id = "idempotency-boundary"
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        uow.canonical.create_topic_identity(
            TopicIdentity(topic_id, topic_id, timestamp, None)
        )
        uow.canonical.create_version(
            CanonicalGraphVersion(
                graph_id,
                "learning-content-fixture-v1",
                "1",
                new_id(),
                CanonicalVersionStatus.PUBLISHED,
                owner.id,
                timestamp,
                timestamp,
                None,
            )
        )
        uow.canonical.add_topic(
            Topic(
                graph_id,
                topic_id,
                "Implement an idempotency boundary",
                "java",
                ("fixture",),
                "Senior",
                "implement",
                "Essential",
                0,
                1,
            )
        )
        for index, layer in enumerate(TopicLayer):
            checkpoint = json.dumps(
                {
                    "scenario": f"{layer.value}: two consumers race.",
                    "constraints": ["Duplicate keys are stable."],
                    "target_capability": "implement",
                    "expected_artifact": "A reviewed Java transaction boundary.",
                    "estimated_minutes": 30 + index,
                    "rubric": ["Names the atomic race arbiter."],
                    "assumptions": ["A unique constraint is available."],
                    "evidence_criterion": "Submit a revision and boundary explanation.",
                    "limitation": "Static review cannot prove runtime behavior.",
                }
            )
            for kind, value in (
                ("layer", f"# {layer.value}\n\nSelf-contained fixture explanation."),
                ("checkpoint", checkpoint),
            ):
                uow.canonical.add_content_revision(
                    ContentRevision(
                        new_id(),
                        graph_id,
                        topic_id,
                        layer.value,
                        kind,
                        "published",
                        _inline(value),
                        f"hash-{index}-{kind}",
                        None,
                        owner.id,
                        None,
                        f"{timestamp}-{index}-{kind}",
                    )
                )
        uow.canonical.record_approval(
            EditorialApproval(
                new_id(),
                graph_id,
                owner.id,
                "designated_editorial_approver",
                "fixture-review",
                timestamp,
            )
        )
        goal = create_goal(
            uow,
            owner.id,
            name="Learn idempotency",
            path=GoalPath.LEARN,
            subject="Java",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.IMPLEMENT,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        uow.commit()
    return graph_id, topic_id, goal.id


def test_topic_and_all_eight_self_contained_layers_are_approval_gated(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    graph_id, topic_id, goal_id = _seed(uow_factory)
    topic = client.get(f"/api/v1/topics/{topic_id}", params={"graph_version": graph_id})
    assert topic.status_code == 200, topic.text
    assert topic.json()["target_capability"] == "implement"

    response = client.get(f"/api/v1/goals/{goal_id}/topics/{topic_id}/layers")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["conversation_scope"] == f"{goal_id}:{topic_id}"
    assert [item["layer"] for item in payload["layers"]] == [
        layer.value for layer in TopicLayer
    ]
    for item in payload["layers"]:
        assert item["state"] == "ready"
        assert item["markdown"].startswith("# ")
        checkpoint = item["checkpoint"]
        assert checkpoint["target_capability"] == "implement"
        assert 30 <= checkpoint["estimated_minutes"] <= 60
        assert checkpoint["scenario"]
        assert checkpoint["expected_artifact"]
        assert checkpoint["rubric"] and checkpoint["assumptions"]
        assert checkpoint["evidence_criterion"] and checkpoint["limitation"]

    layer = client.get(f"/api/v1/goals/{goal_id}/topics/{topic_id}/layers/Production")
    assert layer.status_code == 200
    assert layer.json()["layer"] == "Production"


def test_generation_contract_returns_job_ref_without_claiming_content(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    _graph_id, topic_id, goal_id = _seed(uow_factory)
    response = client.post(
        f"/api/v1/goals/{goal_id}/topics/{topic_id}/generate",
        params={"layer": "Essential"},
        headers={"Idempotency-Key": "generate-essential"},
    )
    assert response.status_code == 202, response.text
    assert response.json()["kind"] == "generate_topic_content"
    assert response.json()["status"] == "failed"

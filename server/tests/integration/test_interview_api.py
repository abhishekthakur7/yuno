"""IDK-301 Interview Prep bundle and read-model contracts."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi.testclient import TestClient

from tests.job_assertions import wait_for_job
from tests.provider_fakes import accept_provider_disclosure, install_provider_fake
from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    Topic,
    TopicIdentity,
)
from yuno.modules.learning_content.domain import (
    GENERATION_CONTRACT_VERSION,
    GENERATION_SCHEMA_VERSION,
    GenerateRequest,
    GenerateResult,
)
from yuno.modules.provenance.domain import Source, SourceAvailability
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id


def _seed_graph(uow_factory: UnitOfWorkFactory, *, suffix: str) -> tuple[str, str]:
    graph_id = new_id()
    topic_id = f"interview-topic-{suffix}"
    timestamp = now_text(SystemClock())
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        uow.canonical.create_topic_identity(
            TopicIdentity(topic_id, topic_id, timestamp, None)
        )
        uow.canonical.create_version(
            CanonicalGraphVersion(
                graph_id,
                f"interview-{suffix}-{graph_id}",
                "v1",
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
                f"Interview topic {suffix}",
                "backend",
                ("fixture",),
                "senior",
                "implement",
                "Essential",
                0,
                1,
            )
        )
        uow.canonical.record_approval(
            EditorialApproval(
                new_id(),
                graph_id,
                owner.id,
                "designated_editorial_approver",
                "IDK-301 fixture",
                timestamp,
            )
        )
        uow.commit()
    return graph_id, topic_id


def _create_goal(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
    *,
    suffix: str,
) -> tuple[str, str]:
    graph_id, topic_id = _seed_graph(uow_factory, suffix=suffix)
    response = client.post(
        "/api/v1/goals",
        headers={"Idempotency-Key": f"interview-goal-{suffix}"},
        json={
            "name": f"Interview {suffix}",
            "path": "interview_prep",
            "role": "Backend Engineer",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": graph_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], topic_id


def _bundle_request(goal_id: str, topic_id: str) -> dict[str, object]:
    return {
        "goal_id": goal_id,
        "name": "Senior backend interview",
        "generic_role": "Backend Engineer",
        "target_level": "Senior",
        "origin": "recommended",
        "items": [
            {
                "subject": "technical",
                "topic_stable_id": topic_id,
                "question": "How do transaction boundaries fail?",
                "position": 0,
                "is_optional": False,
                "included": True,
            },
            {
                "subject": "behavioral",
                "question": "Tell me about a difficult trade-off.",
                "position": 1,
                "is_optional": True,
                "included": True,
            },
            {
                "subject": "leadership",
                "question": "How did you align a team?",
                "position": 2,
                "is_optional": True,
                "included": True,
            },
        ],
    }


def _seed_source(uow_factory: UnitOfWorkFactory, *, suffix: str) -> Source:
    timestamp = now_text(SystemClock())
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        source = Source(
            new_id(),
            owner.id,
            "fixture",
            "documentation",
            f"Interview source {suffix}",
            "Fixture publisher",
            f"https://example.invalid/{suffix}",
            "fixture-approved",
            SourceAvailability.AVAILABLE,
            timestamp,
            timestamp,
        )
        uow.provenance.add_source(source)
        uow.commit()
    return source


@dataclass
class _RefresherGenerationAdapter:
    refs: tuple[tuple[str, str], ...]
    body: str = "A generated interview refresher."
    provider: str = "fixture-provider"
    model: str = "fixture-model-v1"

    def generate(self, request: GenerateRequest) -> GenerateResult:
        return GenerateResult(
            body=self.body,
            provider=self.provider,
            model=self.model,
            contract_version=GENERATION_CONTRACT_VERSION,
            schema_version=GENERATION_SCHEMA_VERSION,
            generated_at=now_text(SystemClock()),
            provenance_refs=self.refs,
        )


def _record_gap(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
    goal_id: str,
    topic_id: str,
    *,
    suffix: str,
) -> tuple[str, str]:
    reason = f"Evidence gap {suffix}: transaction failure recovery is unverified."
    response = client.post(
        f"/api/v1/goals/{goal_id}/corrections",
        headers={"Idempotency-Key": f"interview-gap-{suffix}"},
        json={
            "topic_stable_id": topic_id,
            "classification": "new",
            "correction_type": "gap",
            "reason": reason,
        },
    )
    assert response.status_code == 200, response.text
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        correction = next(
            item
            for item in uow.roadmap.list_corrections(owner.id, goal_id)
            if item.reason == reason
        )
    return correction.id, reason


def _generate_interview_refresher(
    client: TestClient,
    goal_id: str,
    topic_id: str,
    *,
    key: str,
) -> str:
    response = client.post(
        f"/api/v1/goals/{goal_id}/topics/{topic_id}/generate",
        params={"layer": "Interview"},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 202, response.text
    wait_for_job(client, response)
    layer = client.get(f"/api/v1/goals/{goal_id}/topics/{topic_id}/layers/Interview")
    assert layer.status_code == 200, layer.text
    artifact_id = layer.json()["artifact_id"]
    assert artifact_id is not None
    return artifact_id


def _walk_keys(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _item(payload: dict[str, object], subject: str) -> dict[str, object]:
    items = payload["items"]
    assert isinstance(items, list)
    return next(item for item in items if item["subject"] == subject)


def test_bundle_create_copy_are_idempotent_generic_and_independently_editable(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _create_goal(client, uow_factory, suffix="lifecycle")
    request = _bundle_request(goal_id, topic_id)

    company = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": "bundle-company-rejected"},
        json={**request, "company": "Example Corp"},
    )
    assert company.status_code == 422
    invented_level = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": "bundle-invented-level-rejected"},
        json={**request, "target_level": "Principal"},
    )
    assert invented_level.status_code == 422

    created = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": "bundle-create"},
        json=request,
    )
    assert created.status_code == 201, created.text
    source = created.json()
    assert source["goal_id"] == goal_id
    assert source["generic_role"] == "Backend Engineer"
    assert source["target_level"] == "Senior"
    assert source["copy_source_id"] is None
    assert source["row_version"] == 1
    assert "company" not in set(_walk_keys(source))

    company_patch = client.patch(
        f"/api/v1/interview-bundles/{source['id']}",
        headers={"If-Match": str(source["row_version"])},
        json={"company": "Example Corp"},
    )
    assert company_patch.status_code == 422

    company_copy = client.post(
        f"/api/v1/interview-bundles/{source['id']}/copy",
        headers={"Idempotency-Key": "bundle-company-copy-rejected"},
        json={"company": "Example Corp"},
    )
    assert company_copy.status_code == 422

    replay = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": "bundle-create"},
        json=request,
    )
    assert replay.status_code == 201
    assert replay.json() == source
    reused = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": "bundle-create"},
        json={**request, "name": "A different command"},
    )
    assert reused.status_code == 409

    copied = client.post(
        f"/api/v1/interview-bundles/{source['id']}/copy",
        headers={"Idempotency-Key": "bundle-copy"},
        json={"name": "My editable copy"},
    )
    assert copied.status_code == 201, copied.text
    editable = copied.json()
    assert editable["id"] != source["id"]
    assert editable["copy_source_id"] == source["id"]
    assert editable["name"] == "My editable copy"
    assert [item["subject"] for item in editable["items"]] == [
        "technical",
        "behavioral",
        "leadership",
    ]
    assert {item["id"] for item in editable["items"]}.isdisjoint(
        {item["id"] for item in source["items"]}
    )
    copy_replay = client.post(
        f"/api/v1/interview-bundles/{source['id']}/copy",
        headers={"Idempotency-Key": "bundle-copy"},
        json={"name": "My editable copy"},
    )
    assert copy_replay.status_code == 201
    assert copy_replay.json() == editable

    missing_match = client.patch(
        f"/api/v1/interview-bundles/{editable['id']}",
        json={"name": "Missing concurrency guard"},
    )
    assert missing_match.status_code == 412
    patched = client.patch(
        f"/api/v1/interview-bundles/{editable['id']}",
        headers={"If-Match": str(editable["row_version"])},
        json={"name": "Edited independently"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Edited independently"
    assert patched.json()["row_version"] == editable["row_version"] + 1
    stale = client.patch(
        f"/api/v1/interview-bundles/{editable['id']}",
        headers={"If-Match": str(editable["row_version"])},
        json={"name": "Stale overwrite"},
    )
    assert stale.status_code == 412
    source_after = client.get(f"/api/v1/interview-bundles/{source['id']}")
    assert source_after.status_code == 200
    assert source_after.json() == source

    listed = client.get("/api/v1/interview-bundles", params={"goal_id": goal_id})
    assert listed.status_code == 200
    assert {bundle["id"] for bundle in listed.json()} == {
        source["id"],
        editable["id"],
    }
    deleted = client.delete(f"/api/v1/interview-bundles/{editable['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/interview-bundles/{editable['id']}").status_code == 404
    assert [
        bundle["id"]
        for bundle in client.get(
            "/api/v1/interview-bundles", params={"goal_id": goal_id}
        ).json()
    ] == [source["id"]]


def test_optional_item_toggles_do_not_mutate_technical_items(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _create_goal(client, uow_factory, suffix="toggles")
    created = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": "bundle-toggles"},
        json=_bundle_request(goal_id, topic_id),
    )
    assert created.status_code == 201, created.text
    before = created.json()
    technical_before = _item(before, "technical")

    behavioral = _item(before, "behavioral")
    leadership = _item(before, "leadership")
    technical_toggle = client.patch(
        f"/api/v1/interview-bundles/{before['id']}",
        headers={"If-Match": str(before["row_version"])},
        json={"items": [{"id": technical_before["id"], "included": False}]},
    )
    assert technical_toggle.status_code == 422
    assert client.get(f"/api/v1/interview-bundles/{before['id']}").json() == before

    toggled_behavioral = client.patch(
        f"/api/v1/interview-bundles/{before['id']}",
        headers={"If-Match": str(before["row_version"])},
        json={
            "items": [
                {"id": behavioral["id"], "included": False},
            ]
        },
    )
    assert toggled_behavioral.status_code == 200, toggled_behavioral.text
    after_behavioral = toggled_behavioral.json()
    assert _item(after_behavioral, "behavioral")["included"] is False
    assert _item(after_behavioral, "leadership")["included"] is True
    assert _item(after_behavioral, "technical") == technical_before

    toggled_leadership = client.patch(
        f"/api/v1/interview-bundles/{before['id']}",
        headers={"If-Match": str(after_behavioral["row_version"])},
        json={
            "items": [
                {"id": leadership["id"], "included": False},
            ]
        },
    )
    assert toggled_leadership.status_code == 200, toggled_leadership.text
    after_leadership = toggled_leadership.json()
    assert _item(after_leadership, "behavioral")["included"] is False
    assert _item(after_leadership, "leadership")["included"] is False
    assert _item(after_leadership, "technical") == technical_before


def test_questions_are_goal_scoped_and_never_expose_evaluative_feedback(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _create_goal(client, uow_factory, suffix="questions")
    other_goal_id, _ = _create_goal(client, uow_factory, suffix="questions-other")
    created = client.post(
        "/api/v1/interview-bundles",
        headers={"Idempotency-Key": "bundle-questions"},
        json=_bundle_request(goal_id, topic_id),
    )
    assert created.status_code == 201, created.text

    questions = client.get(f"/api/v1/goals/{goal_id}/questions")
    assert questions.status_code == 200, questions.text
    payload = questions.json()
    assert payload
    assert all(question["bundle_id"] == created.json()["id"] for question in payload)
    prohibited = {
        "feedback",
        "facts",
        "trade_offs",
        "trade-offs",
        "rubric",
        "score",
        "evaluation",
    }
    assert prohibited.isdisjoint(set(_walk_keys(payload)))

    other_questions = client.get(f"/api/v1/goals/{other_goal_id}/questions")
    assert other_questions.status_code == 200
    assert other_questions.json() == []
    missing = client.get("/api/v1/goals/not-a-real-goal/questions")
    assert missing.status_code == 404


def test_refreshers_are_goal_scoped_and_do_not_fabricate_missing_links(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, _ = _create_goal(client, uow_factory, suffix="refreshers-empty")

    refreshers = client.get(f"/api/v1/goals/{goal_id}/refreshers")
    assert refreshers.status_code == 200, refreshers.text
    assert refreshers.json() == []

    missing = client.get("/api/v1/goals/not-a-real-goal/refreshers")
    assert missing.status_code == 404


def test_refresher_exposes_real_subject_layer_source_and_evidence_gap_then_stales(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _create_goal(client, uow_factory, suffix="refresher-linked")
    source = _seed_source(uow_factory, suffix="refresher-linked")
    gap_id, gap_reason = _record_gap(
        client,
        uow_factory,
        goal_id,
        topic_id,
        suffix="refresher-linked",
    )
    adapter = _RefresherGenerationAdapter(
        (("source", source.id), ("evidence-gap", gap_id))
    )
    accept_provider_disclosure(client)
    install_provider_fake(client, adapter)
    artifact_id = _generate_interview_refresher(
        client,
        goal_id,
        topic_id,
        key="generate-linked-refresher",
    )

    response = client.get(f"/api/v1/goals/{goal_id}/refreshers")
    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "artifact_id": artifact_id,
            "state": "ready",
            "subject": "backend",
            "layer": "Interview",
            "content": adapter.body,
            "source_ref": source.id,
            "source_title": source.title,
            "evidence_gap_ref": gap_id,
            "evidence_gap": gap_reason,
        }
    ]

    _record_gap(
        client,
        uow_factory,
        goal_id,
        topic_id,
        suffix="refresher-changed",
    )
    stale = client.get(f"/api/v1/goals/{goal_id}/refreshers")
    assert stale.status_code == 200, stale.text
    assert stale.json()[0] == {**response.json()[0], "state": "stale"}


def test_refresher_with_missing_provenance_links_is_explicitly_unavailable(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _create_goal(
        client, uow_factory, suffix="refresher-unavailable"
    )
    adapter = _RefresherGenerationAdapter(())
    accept_provider_disclosure(client)
    install_provider_fake(client, adapter)
    artifact_id = _generate_interview_refresher(
        client,
        goal_id,
        topic_id,
        key="generate-unlinked-refresher",
    )

    response = client.get(f"/api/v1/goals/{goal_id}/refreshers")
    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "artifact_id": artifact_id,
            "state": "unavailable",
            "subject": "backend",
            "layer": "Interview",
            "content": adapter.body,
            "source_ref": None,
            "source_title": None,
            "evidence_gap_ref": None,
            "evidence_gap": None,
        }
    ]

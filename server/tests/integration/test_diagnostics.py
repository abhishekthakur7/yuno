from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from yuno.api.routes import diagnostics as diagnostics_routes
from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    RelationType,
    Topic,
    TopicIdentity,
    TopicRelation,
)
from yuno.modules.diagnostics.service import (
    create_diagnostic,
    record_diagnostic_failure,
)
from yuno.modules.roadmap.repository import SqlAlchemyRoadmapRepository
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id


def _seed_graph(uow_factory: UnitOfWorkFactory) -> tuple[str, str]:
    graph_id = new_id()
    timestamp = now_text(SystemClock())
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        uow.canonical.create_version(
            CanonicalGraphVersion(
                id=graph_id,
                version_label=f"diagnostics-{graph_id}",
                manifest_version="v1",
                manifest_hash=new_id(),
                status=CanonicalVersionStatus.PUBLISHED,
                creator_owner_id=owner.id,
                created_at=timestamp,
                published_at=timestamp,
                supersedes_version_id=None,
            )
        )
        for stable_id, layer in (
            ("fixture-topic-alpha", "Essential"),
            ("fixture-topic-beta", "Implementation"),
        ):
            uow.canonical.create_topic_identity(
                TopicIdentity(
                    stable_id=stable_id,
                    stable_slug=stable_id,
                    created_at=timestamp,
                    retired_at=None,
                )
            )
            uow.canonical.add_topic(
                Topic(
                    graph_version_id=graph_id,
                    stable_id=stable_id,
                    title=stable_id,
                    subject="backend-engineering",
                    scope_tags=("backend-engineering",),
                    level_tag="Senior",
                    target_capability="diagnose",
                    recommended_layer=layer,
                    checkpoint_start=30,
                    checkpoint_end=60,
                )
            )
        uow.canonical.add_relation(
            TopicRelation(
                id=new_id(),
                graph_version_id=graph_id,
                from_stable_id="fixture-topic-alpha",
                to_stable_id="fixture-topic-beta",
                relation_type=RelationType.PREREQUISITE,
                rationale=None,
            )
        )
        uow.canonical.record_approval(
            EditorialApproval(
                id=new_id(),
                graph_version_id=graph_id,
                approver_owner_id=owner.id,
                approver_role="designated_editorial_approver",
                basis_ref="diagnostic-test",
                approved_at=timestamp,
            )
        )
        uow.commit()
    return owner.id, graph_id


def _create(client: TestClient, graph_id: str, key: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/diagnostics",
        headers={"Idempotency-Key": key},
        json={
            "path": "learn",
            "subject": "Distributed systems",
            "target_level": "Senior",
            "target_capability": "diagnose",
            "graph_version_id": graph_id,
            "setup_inputs": {
                "weekly_time": "4 hours",
                "goal_name": "Diagnose distributed systems",
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_pause_refresh_retry_and_optional_skips_preserve_answers(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, graph_id = _seed_graph(uow_factory)
    created = _create(client, graph_id, "create-resumable")
    session_id = str(created["id"])
    first_question = created["next_question"]
    assert isinstance(first_question, dict)
    answered = client.post(
        f"/api/v1/diagnostics/{session_id}/answers",
        headers={"Idempotency-Key": "answer-one"},
        json={
            "question_ref": first_question["ref"],
            "answer": "I am not sure; this is mostly a guess.",
            "confidence": "low",
        },
    )
    assert answered.status_code == 201, answered.text
    replay = client.post(
        f"/api/v1/diagnostics/{session_id}/answers",
        headers={"Idempotency-Key": "answer-one"},
        json={
            "question_ref": first_question["ref"],
            "answer": "I am not sure; this is mostly a guess.",
            "confidence": "low",
        },
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == answered.json()["id"]

    paused = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": "2"},
        json={"action": "pause"},
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["state"] == "paused"
    premature_preview = client.get(f"/api/v1/diagnostics/{session_id}/roadmap-preview")
    assert premature_preview.status_code == 409

    # A new UoW/request reconstructs the aggregate from persisted rows.
    refreshed = client.get(f"/api/v1/diagnostics/{session_id}")
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["question_set_version"] == "diagnostic-fixture-v1"
    assert [item["answer"] for item in body["answers"]] == [
        "I am not sure; this is mostly a guess."
    ]
    assert body["next_question"]["ref"] == "foundation-follow-up"

    with uow_factory() as uow:
        record_diagnostic_failure(
            uow,
            owner_id,
            session_id,
            failure_code="preview_temporarily_unavailable",
            failure_reference="diagnostic-test-ref",
        )
        uow.commit()
    failed = client.get(f"/api/v1/diagnostics/{session_id}").json()
    assert failed["state"] == "failed"
    assert len(failed["answers"]) == 1
    retried = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": str(failed["row_version"])},
        json={"action": "retry"},
    )
    assert retried.status_code == 200, retried.text
    skipped_seed = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": str(retried.json()["row_version"])},
        json={"action": "skip_notes"},
    )
    skipped_diagnostic = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": str(skipped_seed.json()["row_version"])},
        json={"action": "skip_diagnostic"},
    )
    previewed = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": str(skipped_diagnostic.json()["row_version"])},
        json={"action": "open_roadmap_preview"},
    )
    assert previewed.status_code == 200, previewed.text
    preview = client.get(f"/api/v1/diagnostics/{session_id}/roadmap-preview")
    assert preview.status_code == 200
    assert preview.json()["answer_count"] == 1


def test_adaptation_uses_answer_content_and_confidence_and_full_skip_reaches_preview(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    _, graph_id = _seed_graph(uow_factory)
    low = _create(client, graph_id, "create-low")
    high = _create(client, graph_id, "create-high")
    for session, key, answer, confidence in (
        (low, "low-answer", "I am not sure.", "low"),
        (
            high,
            "high-answer",
            "I would examine latency, consistency, and failure trade-offs.",
            "high",
        ),
    ):
        question = session["next_question"]
        response = client.post(
            f"/api/v1/diagnostics/{session['id']}/answers",
            headers={"Idempotency-Key": key},
            json={
                "question_ref": question["ref"],
                "answer": answer,
                "confidence": confidence,
            },
        )
        assert response.status_code == 201, response.text
    low_next = client.get(f"/api/v1/diagnostics/{low['id']}").json()["next_question"][
        "ref"
    ]
    high_next = client.get(f"/api/v1/diagnostics/{high['id']}").json()["next_question"][
        "ref"
    ]
    assert (low_next, high_next) == ("foundation-follow-up", "depth-follow-up")

    skipped = _create(client, graph_id, "create-skipped")
    skip_diagnostic = client.patch(
        f"/api/v1/diagnostics/{skipped['id']}",
        headers={"If-Match": "1"},
        json={"action": "skip_diagnostic"},
    ).json()
    skip_seed = client.patch(
        f"/api/v1/diagnostics/{skipped['id']}",
        headers={"If-Match": str(skip_diagnostic["row_version"])},
        json={"action": "skip_notes"},
    ).json()
    opened = client.patch(
        f"/api/v1/diagnostics/{skipped['id']}",
        headers={"If-Match": str(skip_seed["row_version"])},
        json={"action": "open_roadmap_preview"},
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["state"] == "roadmap-preview"
    assert opened.json()["answers"] == []


def test_owner_scope_and_configured_expiry_are_enforced(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, graph_id = _seed_graph(uow_factory)
    with uow_factory() as uow:
        expired = create_diagnostic(
            uow,
            owner_id,
            captured_graph_version_id=graph_id,
            setup_inputs={
                "path": "learn",
                "subject": "Java",
                "role": None,
                "target_level": "Senior",
                "target_capability": "implement",
            },
            approved_graph_exists=True,
            expires_at="2000-01-01T00:00:00.000000Z",
        )
        uow.commit()
    response = client.get(f"/api/v1/diagnostics/{expired.id}")
    assert response.status_code == 410

    active = _create(client, graph_id, "owner-scope")
    with uow_factory() as uow:
        assert uow.diagnostics.get_session("different-owner", str(active["id"])) is None
        assert uow.diagnostics.list_answers("different-owner", str(active["id"])) == ()


def test_unexpected_answer_failure_persists_retryable_state_and_prior_answers(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
    monkeypatch,
) -> None:
    _, graph_id = _seed_graph(uow_factory)
    created = _create(client, graph_id, "create-failure-boundary")
    session_id = str(created["id"])
    first_question = created["next_question"]
    saved = client.post(
        f"/api/v1/diagnostics/{session_id}/answers",
        headers={"Idempotency-Key": "saved-before-failure"},
        json={
            "question_ref": first_question["ref"],
            "answer": "A durable unique key decides duplicate delivery.",
            "confidence": "high",
        },
    )
    assert saved.status_code == 201

    def fail_answer(*_args, **_kwargs):
        raise RuntimeError("injected diagnostic service failure")

    monkeypatch.setattr(diagnostics_routes, "append_diagnostic_answer", fail_answer)
    next_question_body = client.get(f"/api/v1/diagnostics/{session_id}").json()[
        "next_question"
    ]
    failed = client.post(
        f"/api/v1/diagnostics/{session_id}/answers",
        headers={"Idempotency-Key": "failing-answer"},
        json={
            "question_ref": next_question_body["ref"],
            "answer": "This answer must roll back.",
            "confidence": "medium",
        },
    )
    assert failed.status_code == 503
    assert failed.json()["retryable"] is True
    assert failed.json()["current_state"] == "failed"

    persisted = client.get(f"/api/v1/diagnostics/{session_id}").json()
    assert persisted["state"] == "failed"
    assert [answer["answer"] for answer in persisted["answers"]] == [
        "A durable unique key decides duplicate delivery."
    ]


def test_invalid_preview_replacement_rolls_back_to_last_valid_edits(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    _, graph_id = _seed_graph(uow_factory)
    created = _create(client, graph_id, "preview-validation-create")
    session_id = str(created["id"])
    skipped = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": "1"},
        json={"action": "skip_diagnostic"},
    ).json()
    seed_skipped = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": str(skipped["row_version"])},
        json={"action": "skip_notes"},
    ).json()
    opened = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": str(seed_skipped["row_version"])},
        json={"action": "open_roadmap_preview"},
    )
    assert opened.status_code == 200, opened.text

    valid = client.put(
        f"/api/v1/diagnostics/{session_id}/roadmap-preview",
        json={
            "edits": [
                {
                    "topic_stable_id": "fixture-topic-alpha",
                    "entry_type": "correction",
                    "value": {"classification": "partial"},
                    "reason": "I need more practice",
                }
            ]
        },
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["topic_recommendations"][0]["classification"] == "partial"

    invalid = client.put(
        f"/api/v1/diagnostics/{session_id}/roadmap-preview",
        json={
            "edits": [
                {
                    "entry_type": "order_constraint",
                    "value": {
                        "before_topic_id": "fixture-topic-beta",
                        "after_topic_id": "fixture-topic-alpha",
                    },
                }
            ]
        },
    )
    assert invalid.status_code == 409
    persisted = client.get(f"/api/v1/diagnostics/{session_id}/roadmap-preview").json()
    assert persisted["saved_edits"] == valid.json()["saved_edits"]


def test_confirm_goal_rolls_back_every_side_effect_then_succeeds_once(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    monkeypatch,
) -> None:
    owner_id, graph_id = _seed_graph(uow_factory)
    created = _create(client, graph_id, "atomic-confirm-create")
    session_id = str(created["id"])
    skipped = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": "1"},
        json={"action": "skip_diagnostic"},
    ).json()
    seed_skipped = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": str(skipped["row_version"])},
        json={"action": "skip_notes"},
    ).json()
    previewed = client.patch(
        f"/api/v1/diagnostics/{session_id}",
        headers={"If-Match": str(seed_skipped["row_version"])},
        json={"action": "open_roadmap_preview"},
    )
    assert previewed.status_code == 200, previewed.text
    saved_preview = client.put(
        f"/api/v1/diagnostics/{session_id}/roadmap-preview",
        json={
            "edits": [
                {
                    "topic_stable_id": "fixture-topic-alpha",
                    "entry_type": "depth",
                    "value": {"depth": "Production"},
                    "reason": "Learner chose production depth",
                },
                {
                    "topic_stable_id": "fixture-topic-alpha",
                    "entry_type": "correction",
                    "value": {"classification": "partial"},
                    "reason": "Learner corrected the inference",
                },
            ]
        },
    )
    assert saved_preview.status_code == 200, saved_preview.text

    newer_graph_id = new_id()
    timestamp = now_text(SystemClock())
    with uow_factory() as uow:
        uow.canonical.create_version(
            CanonicalGraphVersion(
                id=newer_graph_id,
                version_label=f"diagnostics-newer-{newer_graph_id}",
                manifest_version="v2",
                manifest_hash=new_id(),
                status=CanonicalVersionStatus.PUBLISHED,
                creator_owner_id=owner_id,
                created_at=timestamp,
                published_at=timestamp,
                supersedes_version_id=graph_id,
            )
        )
        for stable_id, layer in (
            ("fixture-topic-alpha", "Production"),
            ("fixture-topic-beta", "Production"),
        ):
            uow.canonical.add_topic(
                Topic(
                    graph_version_id=newer_graph_id,
                    stable_id=stable_id,
                    title=f"newer-{stable_id}",
                    subject="backend-engineering",
                    scope_tags=("backend-engineering",),
                    level_tag="Senior",
                    target_capability="diagnose",
                    recommended_layer=layer,
                    checkpoint_start=30,
                    checkpoint_end=60,
                )
            )
        uow.canonical.record_approval(
            EditorialApproval(
                id=new_id(),
                graph_version_id=newer_graph_id,
                approver_owner_id=owner_id,
                approver_role="designated_editorial_approver",
                basis_ref="newer-graph-after-diagnostic-start",
                approved_at=timestamp,
            )
        )
        uow.commit()

    def counts() -> dict[str, int]:
        with engine.connect() as connection:
            return {
                table: connection.execute(
                    text(f"SELECT count(*) FROM {table}")
                ).scalar_one()
                for table in (
                    "goal_workspaces",
                    "learning_states",
                    "learner_corrections",
                    "personal_overlays",
                    "overlay_entries",
                    "audit_events",
                    "diagnostics_idempotency",
                )
            }

    baseline = counts()
    original_append = SqlAlchemyRoadmapRepository.append_overlay_entry

    def fail_overlay(*_args, **_kwargs):
        raise RuntimeError("injected overlay write failure")

    monkeypatch.setattr(
        SqlAlchemyRoadmapRepository, "append_overlay_entry", fail_overlay
    )
    failed = client.post(f"/api/v1/diagnostics/{session_id}/confirm-goal")
    assert failed.status_code == 503, failed.text
    assert failed.json()["current_state"] == "roadmap-preview"
    after_failure = counts()
    assert after_failure == baseline
    assert after_failure["goal_workspaces"] == 0
    with uow_factory() as uow:
        profile = uow.profiles_goals.get_profile(owner_id)
        session = uow.diagnostics.get_session(owner_id, session_id)
        assert profile is not None and profile.current_goal_id is None
        assert session is not None
        assert session.state.value == "roadmap-preview"
        assert session.confirmed_goal_id is None
        assert len(uow.diagnostics.list_preview_edits(owner_id, session_id)) == 2

    monkeypatch.setattr(
        SqlAlchemyRoadmapRepository, "append_overlay_entry", original_append
    )
    confirmed = client.post(f"/api/v1/diagnostics/{session_id}/confirm-goal")
    assert confirmed.status_code == 201, confirmed.text
    goal = confirmed.json()
    assert goal["graph_version_id"] == graph_id
    with uow_factory() as uow:
        states = uow.roadmap.list_learning_states(owner_id, goal["id"])
        entries = uow.roadmap.list_overlay_entries(owner_id, goal["id"])
        corrections = uow.roadmap.list_corrections(owner_id, goal["id"])
        session = uow.diagnostics.get_session(owner_id, session_id)
        assert len(states) == 2
        assert {item.topic_stable_id for item in states} == {
            "fixture-topic-alpha",
            "fixture-topic-beta",
        }
        assert all(item.graph_version_id == graph_id for item in states)
        assert len(entries) == 1
        assert entries[0].value == {"depth": "Production"}
        assert len(corrections) == 1
        assert corrections[0].value == "partial"
        assert session is not None and session.confirmed_goal_id == goal["id"]
        assert session.state.value == "confirmed"

    replay = client.post(f"/api/v1/diagnostics/{session_id}/confirm-goal")
    assert replay.status_code == 409, replay.text

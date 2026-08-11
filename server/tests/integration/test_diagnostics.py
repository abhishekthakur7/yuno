from __future__ import annotations

from fastapi.testclient import TestClient

from yuno.api.routes import diagnostics as diagnostics_routes
from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
)
from yuno.modules.diagnostics.service import (
    create_diagnostic,
    record_diagnostic_failure,
)
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
            "setup_inputs": {"weekly_time": "4 hours"},
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

    monkeypatch.setattr(
        diagnostics_routes, "append_diagnostic_answer", fail_answer
    )
    next_question_body = client.get(
        f"/api/v1/diagnostics/{session_id}"
    ).json()["next_question"]
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

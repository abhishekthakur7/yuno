from __future__ import annotations

from datetime import UTC, datetime

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
from yuno.modules.notebook_review.domain import (
    FIXTURE_SCHEDULING_VERSION,
    ReviewItem,
    ReviewItemStatus,
    ReviewPromptType,
)
from yuno.modules.notebook_review.service import create_review_item
from yuno.modules.provenance.domain import Source, SourceAvailability
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import Clock
from yuno.shared.domain.ids import new_id


class FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 8, 12, 12, tzinfo=UTC)


def _create_goal(
    client: TestClient, uow_factory: UnitOfWorkFactory, *, suffix: str
) -> tuple[str, str]:
    topic_id = f"review-topic-{suffix}"
    graph_id = new_id()
    timestamp = "2026-08-01T00:00:00.000000Z"
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        uow.canonical.create_topic_identity(
            TopicIdentity(topic_id, topic_id, timestamp, None)
        )
        uow.canonical.create_version(
            CanonicalGraphVersion(
                graph_id,
                f"review-{suffix}-{graph_id}",
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
                f"Review topic {suffix}",
                "backend",
                ("fixture",),
                "senior",
                "implement",
                "essential",
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
                "IDK-206 fixture",
                timestamp,
            )
        )
        uow.commit()

    response = client.post(
        "/api/v1/goals",
        headers={"Idempotency-Key": f"review-goal-{suffix}"},
        json={
            "name": f"Review {suffix}",
            "path": "learn",
            "subject": "backend",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": graph_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], topic_id


def _create_evidence(
    client: TestClient, goal_id: str, topic_id: str, *, suffix: str
) -> str:
    response = client.post(
        f"/api/v1/goals/{goal_id}/evidence",
        headers={"Idempotency-Key": f"review-evidence-{suffix}"},
        json={
            "topic_stable_id": topic_id,
            "evidence_type": "fixture",
            "capability": "implement",
            "summary": "Review-linked evidence",
            "origin": "test",
            "content": "A preserved response",
            "content_version": "fixture-v1",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _seed_review_item(
    uow_factory: UnitOfWorkFactory,
    goal_id: str,
    topic_id: str,
    prompt_type: ReviewPromptType,
    *,
    suffix: str,
) -> ReviewItem:
    timestamp = "2026-08-01T00:00:00.000000Z"
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        item = ReviewItem(
            new_id(),
            owner.id,
            goal_id,
            topic_id,
            f"prompt-ref-{suffix}",
            prompt_type,
            f"{prompt_type.value.title()} the transaction boundary.",
            f"Hidden {prompt_type.value} answer {suffix}.",
            ReviewItemStatus.DUE,
            timestamp,
            "fixture-next",
            "fixture context",
            FIXTURE_SCHEDULING_VERSION,
            None,
            1,
            timestamp,
            timestamp,
        )
        create_review_item(uow, owner.id, goal_id, item)
        uow.commit()
    return item


def _seed_source(uow_factory: UnitOfWorkFactory, *, suffix: str) -> str:
    timestamp = "2026-08-01T00:00:00.000000Z"
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        source = Source(
            new_id(),
            owner.id,
            "fixture",
            "documentation",
            f"Notebook source {suffix}",
            "Fixture publisher",
            f"https://example.invalid/{suffix}",
            "fixture-approved",
            SourceAvailability.AVAILABLE,
            timestamp,
            timestamp,
        )
        uow.provenance.add_source(source)
        uow.commit()
    return source.id


def test_notebook_crud_links_labels_versions_idempotency_and_soft_tombstone(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _create_goal(client, uow_factory, suffix="notebook")
    evidence_id = _create_evidence(client, goal_id, topic_id, suffix="notebook")
    source_id = _seed_source(uow_factory, suffix="notebook")
    path = f"/api/v1/goals/{goal_id}/notebook"
    request = {
        "entry_kind": "user",
        "markdown": "Initial **learner note**",
        "topic_stable_id": topic_id,
        "evidence_id": evidence_id,
        "source_id": source_id,
    }
    headers = {"Idempotency-Key": "notebook-create-1"}

    created = client.post(path, headers=headers, json=request)
    assert created.status_code == 201, created.text
    entry = created.json()
    assert entry["entry_kind"] == "user"
    assert entry["markdown"] == request["markdown"]
    assert entry["topic_stable_id"] == topic_id
    assert entry["evidence_id"] == evidence_id
    assert entry["source_id"] == source_id
    assert entry["row_version"] == 1

    replay = client.post(path, headers=headers, json=request)
    assert replay.status_code == 201
    assert replay.json() == entry
    reused = client.post(
        path, headers=headers, json={**request, "markdown": "different"}
    )
    assert reused.status_code == 409
    assert reused.json()["code"] == "idempotency_key_reused"

    listed = client.get(path)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [entry["id"]]

    patched = client.patch(
        f"/api/v1/notebook/{entry['id']}",
        headers={
            "If-Match": str(entry["row_version"]),
            "Idempotency-Key": "notebook-patch-1",
        },
        json={"markdown": "Revised note", "evidence_id": None},
    )
    assert patched.status_code == 200, patched.text
    revised = patched.json()
    assert revised["markdown"] == "Revised note"
    assert revised["entry_kind"] == "user"
    assert revised["evidence_id"] is None
    assert revised["row_version"] == 2

    stale = client.patch(
        f"/api/v1/notebook/{entry['id']}",
        headers={"If-Match": "1", "Idempotency-Key": "notebook-patch-stale"},
        json={"markdown": "stale overwrite"},
    )
    assert stale.status_code == 412
    relabel = client.patch(
        f"/api/v1/notebook/{entry['id']}",
        headers={
            "If-Match": str(revised["row_version"]),
            "Idempotency-Key": "notebook-relabel-forbidden",
        },
        json={"entry_kind": "auto"},
    )
    assert relabel.status_code == 422

    deleted = client.delete(
        f"/api/v1/notebook/{entry['id']}",
        headers={
            "If-Match": str(revised["row_version"]),
            "Idempotency-Key": "notebook-delete-1",
        },
    )
    assert deleted.status_code == 204, deleted.text
    assert client.get(path).json() == []
    gone = client.patch(
        f"/api/v1/notebook/{entry['id']}",
        headers={
            "If-Match": str(revised["row_version"] + 1),
            "Idempotency-Key": "notebook-patch-gone",
        },
        json={"markdown": "must remain gone"},
    )
    assert gone.status_code == 410

    with engine.connect() as connection:
        stored = connection.execute(
            text(
                "SELECT n.entry_kind, b.markdown, n.tombstoned_at "
                "FROM notebook_entries n JOIN notebook_entry_bodies b "
                "ON b.entry_id=n.id WHERE n.id = :id"
            ),
            {"id": entry["id"]},
        ).one()
    assert stored.entry_kind == "user"
    assert stored.markdown == "Revised note"
    assert stored.tombstoned_at is not None


def test_notebook_rejects_missing_label_blank_markdown_and_out_of_scope_links(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _create_goal(client, uow_factory, suffix="links-a")
    other_goal_id, other_topic_id = _create_goal(client, uow_factory, suffix="links-b")
    other_evidence_id = _create_evidence(
        client, other_goal_id, other_topic_id, suffix="links-b"
    )
    path = f"/api/v1/goals/{goal_id}/notebook"

    missing_label = client.post(
        path,
        headers={"Idempotency-Key": "notebook-missing-label"},
        json={"markdown": "No provenance label"},
    )
    assert missing_label.status_code == 422
    blank = client.post(
        path,
        headers={"Idempotency-Key": "notebook-blank"},
        json={"entry_kind": "user", "markdown": "  \n  "},
    )
    assert blank.status_code == 422

    for suffix, expected_status, link in (
        ("topic", 422, {"topic_stable_id": other_topic_id}),
        ("evidence", 404, {"evidence_id": other_evidence_id}),
        ("source", 404, {"source_id": "source-outside-owner-scope"}),
    ):
        response = client.post(
            path,
            headers={"Idempotency-Key": f"notebook-invalid-{suffix}"},
            json={"entry_kind": "auto", "markdown": "Linked note", **link},
        )
        assert response.status_code == expected_status, (suffix, response.text)

    valid = client.post(
        path,
        headers={"Idempotency-Key": "notebook-valid-topic"},
        json={
            "entry_kind": "auto",
            "markdown": "Valid auto note",
            "topic_stable_id": topic_id,
        },
    )
    assert valid.status_code == 201, valid.text
    assert valid.json()["entry_kind"] == "auto"


def test_patch_contracts_reject_explicit_null_for_required_values(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, _ = _create_goal(client, uow_factory, suffix="patch-nulls")
    created = client.post(
        f"/api/v1/goals/{goal_id}/notebook",
        headers={"Idempotency-Key": "patch-null-entry"},
        json={"entry_kind": "user", "markdown": "Keep this entry."},
    )
    assert created.status_code == 201, created.text

    notebook_patch = client.patch(
        f"/api/v1/notebook/{created.json()['id']}",
        headers={"If-Match": "1"},
        json={"markdown": None},
    )
    assert notebook_patch.status_code == 422

    for field in (
        "enabled",
        "duration_minutes",
        "cadence",
        "retrieval_enabled",
        "varied_context_enabled",
    ):
        preferences_patch = client.patch(
            f"/api/v1/goals/{goal_id}/review-preferences",
            headers={"If-Match": "1"},
            json={field: None},
        )
        assert preferences_patch.status_code == 422, (
            field,
            preferences_patch.text,
        )


def test_generation_failed_review_reports_retryable_without_blocking_queue(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _create_goal(client, uow_factory, suffix="generation-failed")
    timestamp = "2026-08-01T00:00:00.000000Z"
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        failed = ReviewItem(
            new_id(),
            owner.id,
            goal_id,
            topic_id,
            "prompt-ref-generation-failed",
            ReviewPromptType.RECALL,
            "Prompt generation failed.",
            None,
            ReviewItemStatus.GENERATION_FAILED,
            None,
            None,
            None,
            FIXTURE_SCHEDULING_VERSION,
            "review-generation:fixture",
            1,
            timestamp,
            timestamp,
        )
        create_review_item(uow, owner.id, goal_id, failed)
        uow.commit()

    response = client.get(f"/api/v1/goals/{goal_id}/reviews")
    assert response.status_code == 200, response.text
    [item] = response.json()["items"]
    assert item["id"] == failed.id
    assert item["status"] == "generation-failed"
    assert item["answer"] is None
    assert item["failure_reference"] == "review-generation:fixture"
    assert item["retryable"] is True


def test_review_preferences_are_goal_scoped_versioned_and_validated(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, _ = _create_goal(client, uow_factory, suffix="preferences")
    path = f"/api/v1/goals/{goal_id}/review-preferences"
    initial = client.get(path)
    assert initial.status_code == 200, initial.text
    preferences = initial.json()
    assert {
        key: preferences[key]
        for key in (
            "goal_id",
            "enabled",
            "duration_minutes",
            "cadence",
            "retrieval_enabled",
            "varied_context_enabled",
            "scheduling_version",
            "row_version",
        )
    } == {
        "goal_id": goal_id,
        "enabled": True,
        "duration_minutes": 15,
        "cadence": "twice-weekly",
        "retrieval_enabled": True,
        "varied_context_enabled": True,
        "scheduling_version": "fixture-v0",
        "row_version": 1,
    }

    updated = client.patch(
        path,
        headers={
            "If-Match": str(preferences["row_version"]),
            "Idempotency-Key": "review-preferences-update",
        },
        json={
            "duration_minutes": 25,
            "cadence": "three-times-weekly",
            "retrieval_enabled": False,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["row_version"] == 2
    assert updated.json()["duration_minutes"] == 25
    assert updated.json()["cadence"] == "three-times-weekly"
    assert updated.json()["retrieval_enabled"] is False

    stale = client.patch(
        path,
        headers={"If-Match": "1", "Idempotency-Key": "review-preferences-stale"},
        json={"enabled": False},
    )
    assert stale.status_code == 412
    invalid = client.patch(
        path,
        headers={"If-Match": "2", "Idempotency-Key": "review-preferences-invalid"},
        json={"duration_minutes": 999},
    )
    assert invalid.status_code == 422


def test_every_retrieval_prompt_redacts_answer_until_a_nonblank_attempt_commits(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _create_goal(client, uow_factory, suffix="recall-before-reveal")
    items = [
        _seed_review_item(
            uow_factory, goal_id, topic_id, prompt_type, suffix=prompt_type.value
        )
        for prompt_type in ReviewPromptType
    ]
    path = f"/api/v1/goals/{goal_id}/reviews"

    listed = client.get(path)
    assert listed.status_code == 200, listed.text
    assert listed.json()["goal_id"] == goal_id
    assert listed.json()["enabled"]
    assert listed.json()["scheduling_version"] == FIXTURE_SCHEDULING_VERSION
    before = {item["id"]: item for item in listed.json()["items"]}
    assert set(before) == {item.id for item in items}
    for item in items:
        assert before[item.id]["prompt_type"] == item.prompt_type.value
        assert before[item.id]["answer"] is None

        rejected = client.post(
            f"/api/v1/reviews/{item.id}/attempts",
            headers={"Idempotency-Key": f"blank-{item.prompt_type.value}"},
            json={"response": " \n ", "confidence": "medium"},
        )
        assert rejected.status_code == 422
        still_hidden = {
            value["id"]: value for value in client.get(path).json()["items"]
        }
        assert still_hidden[item.id]["answer"] is None

        attempted = client.post(
            f"/api/v1/reviews/{item.id}/attempts",
            headers={"Idempotency-Key": f"attempt-{item.prompt_type.value}"},
            json={
                "response": f"Learner {item.prompt_type.value} response",
                "confidence": "medium",
                "context_result": "Applied in a varied fixture context",
            },
        )
        assert attempted.status_code == 201, attempted.text
        result = attempted.json()
        assert result["review_item_id"] == item.id
        assert result["review_status"] == "completed"
        assert result["revealed_answer"] == item.answer
        assert result["scheduling_version"] == FIXTURE_SCHEDULING_VERSION
        replay = client.post(
            f"/api/v1/reviews/{item.id}/attempts",
            headers={"Idempotency-Key": f"attempt-{item.prompt_type.value}"},
            json={
                "response": f"Learner {item.prompt_type.value} response",
                "confidence": "medium",
                "context_result": "Applied in a varied fixture context",
            },
        )
        assert replay.status_code == 201
        assert replay.json() == result
        reused = client.post(
            f"/api/v1/reviews/{item.id}/attempts",
            headers={"Idempotency-Key": f"attempt-{item.prompt_type.value}"},
            json={"response": "Different replay payload"},
        )
        assert reused.status_code == 409
        assert reused.json()["code"] == "idempotency_key_reused"

    after = {item["id"]: item for item in client.get(path).json()["items"]}
    assert all(after[item.id]["answer"] == item.answer for item in items)

    attempt_id = client.post(
        f"/api/v1/reviews/{items[0].id}/attempts",
        headers={"Idempotency-Key": "second-attempt-invalid-state"},
        json={"response": "Cannot overwrite the completed attempt"},
    )
    assert attempt_id.status_code == 409

    with engine.connect() as connection:
        persisted = connection.execute(
            text(
                "SELECT a.id, b.response FROM review_attempts a "
                "JOIN review_attempt_bodies b ON b.attempt_id=a.id "
                "WHERE a.review_item_id = :review_id ORDER BY a.created_at"
            ),
            {"review_id": items[0].id},
        ).one()
    with (
        pytest.raises(IntegrityError, match="review_attempts header is immutable"),
        engine.begin() as connection,
    ):
        connection.execute(
            text(
                "UPDATE review_attempts SET scheduling_version = 'rewritten' "
                "WHERE id = :id"
            ),
            {"id": persisted.id},
        )
    with (
        pytest.raises(IntegrityError, match="review_attempts header is immutable"),
        engine.begin() as connection,
    ):
        connection.execute(
            text("DELETE FROM review_attempts WHERE id = :id"),
            {"id": persisted.id},
        )


def _progress_rows(engine: Engine, goal_id: str) -> list[tuple[object, ...]]:
    with engine.connect() as connection:
        return [
            tuple(row)
            for row in connection.execute(
                text("SELECT * FROM goal_progress_memos WHERE goal_id = :goal_id"),
                {"goal_id": goal_id},
            ).all()
        ]


def test_dismiss_and_disable_have_exactly_zero_progress_delta_and_never_gate_roadmap(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    client.app.state.clock = FixedClock()
    goal_id, topic_id = _create_goal(client, uow_factory, suffix="zero-delta")
    dismiss_item = _seed_review_item(
        uow_factory,
        goal_id,
        topic_id,
        ReviewPromptType.RECALL,
        suffix="dismiss-zero-delta",
    )

    progress_path = f"/api/v1/goals/{goal_id}/progress"
    roadmap_path = f"/api/v1/goals/{goal_id}/roadmap"
    baseline_response = client.get(progress_path)
    assert baseline_response.status_code == 200, baseline_response.text
    baseline = baseline_response.json()
    baseline_rows = _progress_rows(engine, goal_id)
    assert len(baseline_rows) == 1
    assert client.get(roadmap_path).status_code == 200

    dismissed = client.post(
        f"/api/v1/reviews/{dismiss_item.id}/dismiss",
        headers={
            "Idempotency-Key": "dismiss-zero-delta",
            "If-Match": str(dismiss_item.row_version),
        },
    )
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["status"] == "dismissed"
    assert dismissed.json()["answer"] is None
    dismiss_replay = client.post(
        f"/api/v1/reviews/{dismiss_item.id}/dismiss",
        headers={"Idempotency-Key": "dismiss-zero-delta"},
    )
    assert dismiss_replay.status_code == 200
    assert dismiss_replay.json() == dismissed.json()
    assert client.get(progress_path).json() == baseline
    assert _progress_rows(engine, goal_id) == baseline_rows
    assert client.get(roadmap_path).status_code == 200

    disable_item = _seed_review_item(
        uow_factory,
        goal_id,
        topic_id,
        ReviewPromptType.APPLICATION,
        suffix="disable-zero-delta",
    )
    preferences_path = f"/api/v1/goals/{goal_id}/review-preferences"
    preferences = client.get(preferences_path).json()
    disabled = client.patch(
        preferences_path,
        headers={
            "If-Match": str(preferences["row_version"]),
            "Idempotency-Key": "disable-review-zero-delta",
        },
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False

    queue_response = client.get(f"/api/v1/goals/{goal_id}/reviews").json()
    assert queue_response["enabled"] is False
    queue = {item["id"]: item for item in queue_response["items"]}
    assert queue[disable_item.id]["status"] == "disabled"
    assert queue[disable_item.id]["answer"] is None
    assert client.get(progress_path).json() == baseline
    assert _progress_rows(engine, goal_id) == baseline_rows
    assert client.get(roadmap_path).status_code == 200

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from tests.fixtures.canonical import load_fixture
from yuno.modules.canonical.models import (
    CanonicalMergeFollowupRow,
    CanonicalMergeProposalRow,
    MergeItemRow,
)
from yuno.modules.canonical.publisher import publish_canonical_graph
from yuno.modules.canonical.repository import SqlAlchemyCanonicalMergeRepository
from yuno.modules.identity.domain import Role
from yuno.modules.imports.domain import ImportType
from yuno.modules.imports.service import create_import
from yuno.modules.profiles_goals.domain import GoalPath, TargetCapability, TargetLevel
from yuno.modules.profiles_goals.service import create_goal
from yuno.modules.roadmap.models import OverlayEntryRow, PersonalOverlayRow
from yuno.shared.application.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True)
class MergeFixture:
    owner_id: str
    goal_id: str
    base_version_id: str
    target_version_id: str | None


def _publish(
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    fixture_name: str,
):
    fixture = load_fixture(fixture_name)
    assert fixture.approval is not None
    return publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=fixture.manifest,
        actor_owner_id=owner_id,
        basis_ref=fixture.approval.basis_ref,
        topic_identity_slugs=fixture.topic_identity_slugs,
    )


def _setup(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    *,
    publish_target: bool = True,
    local_state: bool = False,
    imported: bool = False,
) -> MergeFixture:
    # Starting the client provisions the same singleton owner/profile used by
    # production requests. The publisher then exercises the real offline path.
    client.get("/api/v1/health")
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        if Role.DESIGNATED_EDITORIAL_APPROVER not in uow.owners.grants(owner.id):
            uow.owners.grant_role(
                owner.id,
                Role.DESIGNATED_EDITORIAL_APPROVER,
                assigned_by_owner_id=owner.id,
            )
        uow.commit()

    base = _publish(engine, uow_factory, owner.id, "v1_approved")
    with uow_factory() as uow:
        goal = create_goal(
            uow,
            owner.id,
            name="Canonical merge fixture",
            path=GoalPath.LEARN,
            subject="Java",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.IMPLEMENT,
            graph_version_id=base.id,
            approved_graph_exists=True,
        )
        if imported:
            create_import(
                uow,
                owner.id,
                goal_id=goal.id,
                import_type=ImportType.PLAIN_TEXT,
                source_text="An unmapped statement to reprocess after adoption.",
            )
        uow.commit()

    if local_state:
        overlay_conflict = client.post(
            f"/api/v1/goals/{goal.id}/depth-overrides",
            headers={"Idempotency-Key": "merge-fixture-overlay"},
            json={"topic_stable_id": "fixture-topic-alpha", "depth": "Internals"},
        )
        assert overlay_conflict.status_code == 200, overlay_conflict.text
        deleted_topic_state = client.post(
            f"/api/v1/goals/{goal.id}/skip-decisions",
            headers={"Idempotency-Key": "merge-fixture-deleted-topic"},
            json={"topic_stable_id": "fixture-topic-gamma", "skipped": True},
        )
        assert deleted_topic_state.status_code == 200, deleted_topic_state.text

    target = (
        _publish(engine, uow_factory, owner.id, "v2_approved")
        if publish_target
        else None
    )
    return MergeFixture(owner.id, goal.id, base.id, target.id if target else None)


def _proposal(client: TestClient, goal_id: str) -> dict:
    response = client.get(f"/api/v1/goals/{goal_id}/canonical-update")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proposal"] is not None
    return body


def _complete_items(proposal: dict) -> list[dict]:
    return [
        {
            "item_id": item["id"],
            "selected": True,
            "resolution": (
                item["recommended_resolution"] if item["conflict_type"] else None
            ),
        }
        for item in proposal["items"]
    ]


def _database_state(engine: Engine, fixture: MergeFixture, proposal_id: str) -> dict:
    with engine.connect() as connection:
        return {
            "goal_pin": connection.exec_driver_sql(
                "SELECT graph_version_id FROM goal_workspaces WHERE id = ?",
                (fixture.goal_id,),
            ).scalar_one(),
            "overlay": connection.execute(
                select(
                    PersonalOverlayRow.base_graph_version_id,
                    PersonalOverlayRow.row_version,
                ).where(PersonalOverlayRow.goal_id == fixture.goal_id)
            ).one_or_none(),
            "entries": connection.execute(
                select(func.count()).select_from(OverlayEntryRow).where(
                    OverlayEntryRow.goal_id == fixture.goal_id
                )
            ).scalar_one(),
            "proposal": connection.execute(
                select(CanonicalMergeProposalRow.status).where(
                    CanonicalMergeProposalRow.id == proposal_id
                )
            ).scalar_one(),
            "resolved": connection.execute(
                select(func.count()).select_from(MergeItemRow).where(
                    MergeItemRow.proposal_id == proposal_id,
                    MergeItemRow.chosen_resolution.is_not(None),
                )
            ).scalar_one(),
        }


def test_update_is_empty_at_latest_and_real_v1_to_v2_diff_is_direct(
    client: TestClient, engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    latest = _setup(client, engine, uow_factory, publish_target=False)
    empty = client.get(f"/api/v1/goals/{latest.goal_id}/canonical-update")
    assert empty.status_code == 200
    assert empty.json() == {
        "state": "empty",
        "goal_id": latest.goal_id,
        "base_version": {
            "id": latest.base_version_id,
            "version_label": "fixture-canonical-v1",
        },
        "target_version": None,
        "proposal": None,
    }

    target = _publish(engine, uow_factory, latest.owner_id, "v2_approved")
    update = _proposal(client, latest.goal_id)
    assert update["base_version"] == {
        "id": latest.base_version_id,
        "version_label": "fixture-canonical-v1",
    }
    assert update["target_version"] == {
        "id": target.id,
        "version_label": "fixture-canonical-v2",
    }


def test_get_computes_overlay_wins_defaults_without_persisting_review_choices(
    client: TestClient, engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    fixture = _setup(client, engine, uow_factory, local_state=True)
    update = _proposal(client, fixture.goal_id)

    assert update["base_version"]["id"] == fixture.base_version_id
    assert update["target_version"]["id"] == fixture.target_version_id
    assert update["state"] == "conflict-needs-resolution"
    overlay_conflict = next(
        item for item in update["proposal"]["items"]
        if item["conflict_type"] == "overlay-conflict"
    )
    assert overlay_conflict["selected"] is True
    assert overlay_conflict["recommended_resolution"] == "overlay-wins"
    assert overlay_conflict["chosen_resolution"] is None
    assert "local choice stays in control" in overlay_conflict[
        "resolution_explanation"
    ].lower()

    with engine.connect() as connection:
        stored = connection.execute(
            select(MergeItemRow.selected, MergeItemRow.chosen_resolution).where(
                MergeItemRow.id == overlay_conflict["id"]
            )
        ).one()
    assert stored == (1, None)


def test_accept_rejects_unresolved_and_stale_proposals_without_partial_writes(
    client: TestClient, engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    fixture = _setup(client, engine, uow_factory, local_state=True)
    proposal = _proposal(client, fixture.goal_id)["proposal"]
    items = _complete_items(proposal)
    conflict = next(item for item in proposal["items"] if item["conflict_type"])
    next(item for item in items if item["item_id"] == conflict["id"])["resolution"] = None
    before = _database_state(engine, fixture, proposal["id"])

    unresolved = client.post(
        f"/api/v1/canonical-update-proposals/{proposal['id']}/accept",
        headers={"Idempotency-Key": "unresolved-merge"},
        json={"confirmed": True, "items": items},
    )
    assert unresolved.status_code == 409
    assert conflict["id"] in unresolved.json()["message"]
    assert _database_state(engine, fixture, proposal["id"]) == before

    with uow_factory() as uow:
        goal = uow.profiles_goals.get_goal(fixture.owner_id, fixture.goal_id)
        assert goal is not None
        assert uow.profiles_goals.update_goal(
            fixture.owner_id,
            fixture.goal_id,
            goal.row_version,
            {"name": "Changed concurrently"},
        ) is not None
        uow.commit()
    complete = _complete_items(proposal)
    stale = client.post(
        f"/api/v1/canonical-update-proposals/{proposal['id']}/accept",
        headers={"Idempotency-Key": "stale-merge"},
        json={"confirmed": True, "items": complete},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "proposal_stale"
    after_stale = _database_state(engine, fixture, proposal["id"])
    assert after_stale["goal_pin"] == fixture.base_version_id
    assert after_stale["overlay"] == before["overlay"]
    assert after_stale["entries"] == before["entries"]
    assert after_stale["proposal"] == "awaiting"
    assert after_stale["resolved"] == 0


def test_accept_rejects_invalid_selection_resolution_combinations(
    client: TestClient, engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    fixture = _setup(client, engine, uow_factory, local_state=True)
    proposal = _proposal(client, fixture.goal_id)["proposal"]
    baseline = _database_state(engine, fixture, proposal["id"])
    overlay_conflict = next(
        item for item in proposal["items"]
        if item["conflict_type"] == "overlay-conflict"
    )
    deleted_local = next(
        item for item in proposal["items"]
        if item["conflict_type"] == "local-state-on-deleted-topic"
    )
    ordinary = next(item for item in proposal["items"] if not item["conflict_type"])
    cases = (
        (ordinary["id"], False, None),
        (ordinary["id"], True, "retain-local"),
        (overlay_conflict["id"], True, "retain-local"),
        (deleted_local["id"], True, "accept-canonical"),
    )

    for index, (item_id, selected, resolution) in enumerate(cases):
        items = _complete_items(proposal)
        choice = next(item for item in items if item["item_id"] == item_id)
        choice.update(selected=selected, resolution=resolution)
        response = client.post(
            f"/api/v1/canonical-update-proposals/{proposal['id']}/accept",
            headers={"Idempotency-Key": f"invalid-merge-choice-{index}"},
            json={"confirmed": True, "items": items},
        )
        assert response.status_code == 409
        assert item_id in response.json()["message"]
        assert _database_state(engine, fixture, proposal["id"]) == baseline


def test_complete_accept_is_atomic_archives_local_topic_and_is_idempotent(
    client: TestClient, engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    fixture = _setup(
        client, engine, uow_factory, local_state=True, imported=True
    )
    proposal = _proposal(client, fixture.goal_id)["proposal"]
    items = _complete_items(proposal)
    deleted = next(
        item for item in proposal["items"]
        if item["conflict_type"] == "local-state-on-deleted-topic"
    )
    deleted_choice = next(item for item in items if item["item_id"] == deleted["id"])
    deleted_choice.update(selected=False, resolution="retain-local")
    retained = next(
        item for item in proposal["items"]
        if item["conflict_type"] is None
        and item["change_type"] == "modified"
        and item["entity_type"] in ("topic", "relation")
    )
    retained_choice = next(item for item in items if item["item_id"] == retained["id"])
    retained_choice.update(selected=False, resolution="retain-local")
    request = {"confirmed": True, "items": items}

    accepted = client.post(
        f"/api/v1/canonical-update-proposals/{proposal['id']}/accept",
        headers={"Idempotency-Key": "accept-canonical-v2"},
        json=request,
    )
    assert accepted.status_code == 200, accepted.text
    result = accepted.json()
    assert result["status"] == "accepted"
    assert result["base_version_id"] == fixture.base_version_id
    assert result["target_version_id"] == fixture.target_version_id
    assert result["goal_graph_version_id"] == fixture.target_version_id
    assert result["invalidation_state"] == "pending-dispatch"
    assert result["reprocess_job"] is None

    roadmap = client.get(f"/api/v1/goals/{fixture.goal_id}/roadmap")
    assert roadmap.status_code == 200, roadmap.text
    projection = roadmap.json()
    assert projection["graph_version_id"] == fixture.target_version_id
    archived = next(
        topic for topic in projection["topics"]
        if topic["stable_id"] == "fixture-topic-gamma"
    )
    assert archived["is_archived_local"] is True
    assert archived["title"] == "[SYNTHETIC] Fixture Topic Gamma"
    alpha = next(
        topic for topic in projection["topics"]
        if topic["stable_id"] == "fixture-topic-alpha"
    )
    assert alpha["depth_override"] == "Internals"

    with uow_factory() as uow:
        goal = uow.profiles_goals.get_goal(fixture.owner_id, fixture.goal_id)
        assert goal is not None and goal.graph_version_id == fixture.target_version_id
        stored_items = {
            item.id: item
            for item in uow.canonical_merges.list_merge_items(
                fixture.owner_id, proposal["id"]
            )
        }
        assert all(item.chosen_resolution is not None for item in stored_items.values())
        assert stored_items[deleted["id"]].selected is False
        assert stored_items[retained["id"]].selected is False
        entries = uow.roadmap.list_overlay_entries(fixture.owner_id, fixture.goal_id)
        merge_entries = [
            entry for entry in entries
            if entry.graph_version_id == fixture.target_version_id
        ]
        assert any(
            entry.entry_type.value == "archived_local_topic"
            and entry.topic_stable_id == "fixture-topic-gamma"
            for entry in merge_entries
        )
        assert any(
            entry.entry_type.value == "merge_resolution"
            and entry.value.get("merge_item_id") == retained["id"]
            and entry.value.get("retained") is True
            and entry.value.get("change_type") == "modified"
            and entry.value.get("before")
            for entry in merge_entries
        )
        assert any(
            entry.entry_type.value == "depth"
            and entry.topic_stable_id == "fixture-topic-alpha"
            and entry.value == {"depth": "Internals"}
            and entry.supersedes_entry_id is not None
            for entry in merge_entries
        )
        audits = uow.audit.list_for_owner(fixture.owner_id)
        assert any(
            event.entity_id == proposal["id"] and event.action == "accepted"
            for event in audits
        )
        followups = uow.canonical_merges.list_merge_followups(
            fixture.owner_id, proposal["id"]
        )
        by_kind = {followup.kind: followup for followup in followups}
        assert set(by_kind) == {
            "generated_content",
            "reprocess_import",
            "roadmap",
            "search",
        }
        assert by_kind["reprocess_import"].status == "dispatched"
        assert by_kind["reprocess_import"].job_id is not None
        assert by_kind["roadmap"].status == "completed-derived"
        assert by_kind["generated_content"].status == "completed-derived"
        assert by_kind["search"].status == "pending-dispatch"

    replay = client.post(
        f"/api/v1/canonical-update-proposals/{proposal['id']}/accept",
        headers={"Idempotency-Key": "accept-canonical-v2"},
        json=request,
    )
    assert replay.status_code == 200
    assert replay.json() == result
    changed = {"confirmed": True, "items": [dict(item) for item in items]}
    changed["items"][0]["selected"] = not changed["items"][0]["selected"]
    changed["items"][0]["resolution"] = (
        "retain-local" if not changed["items"][0]["selected"] else "accept-canonical"
    )
    conflict = client.post(
        f"/api/v1/canonical-update-proposals/{proposal['id']}/accept",
        headers={"Idempotency-Key": "accept-canonical-v2"},
        json=changed,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_key_reused"


def test_mid_accept_failure_rolls_back_pin_resolutions_overlay_and_proposal(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _setup(client, engine, uow_factory, local_state=True)
    proposal = _proposal(client, fixture.goal_id)["proposal"]
    before = _database_state(engine, fixture, proposal["id"])

    def fail_after_accept_writes(*args, **kwargs):
        raise RuntimeError("injected canonical acceptance failure")

    monkeypatch.setattr(
        SqlAlchemyCanonicalMergeRepository,
        "close_merge_proposal",
        fail_after_accept_writes,
    )
    with pytest.raises(RuntimeError, match="injected canonical acceptance failure"):
        client.post(
            f"/api/v1/canonical-update-proposals/{proposal['id']}/accept",
            headers={"Idempotency-Key": "rollback-canonical-v2"},
            json={"confirmed": True, "items": _complete_items(proposal)},
        )

    assert _database_state(engine, fixture, proposal["id"]) == before
    with engine.connect() as connection:
        assert connection.execute(
            select(func.count()).select_from(CanonicalMergeFollowupRow).where(
                CanonicalMergeFollowupRow.proposal_id == proposal["id"]
            )
        ).scalar_one() == 0


@pytest.mark.parametrize("decision", ["postpone", "dismiss"])
def test_postpone_and_dismiss_leave_pin_overlay_and_roadmap_unchanged(
    decision: str,
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    fixture = _setup(client, engine, uow_factory, local_state=True)
    proposal = _proposal(client, fixture.goal_id)["proposal"]
    before_db = _database_state(engine, fixture, proposal["id"])
    before_roadmap = client.get(f"/api/v1/goals/{fixture.goal_id}/roadmap").json()

    response = client.post(
        f"/api/v1/canonical-update-proposals/{proposal['id']}/decision",
        headers={"Idempotency-Key": f"canonical-{decision}"},
        json={"decision": decision, "reason": "Learner chose not to adopt now."},
    )
    assert response.status_code == 200, response.text
    expected_status = {"postpone": "postponed", "dismiss": "dismissed"}[decision]
    assert response.json()["status"] == expected_status

    after_db = _database_state(engine, fixture, proposal["id"])
    assert after_db["goal_pin"] == before_db["goal_pin"]
    assert after_db["overlay"] == before_db["overlay"]
    assert after_db["entries"] == before_db["entries"]
    assert after_db["resolved"] == before_db["resolved"] == 0
    assert after_db["proposal"] == expected_status
    assert client.get(f"/api/v1/goals/{fixture.goal_id}/roadmap").json() == before_roadmap

from __future__ import annotations

import pytest
from sqlalchemy import text

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    Topic,
    TopicIdentity,
)
from yuno.modules.evidence_evaluation.domain import (
    Evidence,
    EvidencePayload,
    TransferClassification,
)
from yuno.modules.evidence_evaluation.service import (
    create_delete_preflight,
    delete_goal,
    transfer_evidence,
)
from yuno.modules.profiles_goals.domain import GoalPath, TargetCapability, TargetLevel
from yuno.modules.profiles_goals.service import create_goal
from yuno.modules.roadmap.repository import SqlAlchemyRoadmapRepository
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import ConflictError
from yuno.shared.domain.ids import new_id


def _seed(uow_factory: UnitOfWorkFactory):
    timestamp = now_text(SystemClock())
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        graph_id = new_id()
        uow.canonical.create_topic_identity(
            TopicIdentity("queues", "queues", timestamp, None)
        )
        uow.canonical.create_version(
            CanonicalGraphVersion(
                graph_id,
                "evidence-v1",
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
                "queues",
                "Queues",
                "dsa",
                ("fixture",),
                "Senior",
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
                "test",
                timestamp,
            )
        )
        source = create_goal(
            uow,
            owner.id,
            name="Source",
            path=GoalPath.LEARN,
            subject="DSA",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.IMPLEMENT,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        target = create_goal(
            uow,
            owner.id,
            name="Target",
            path=GoalPath.LEARN,
            subject="DSA",
            role=None,
            target_level=TargetLevel.STAFF,
            target_capability=TargetCapability.DEFEND,
            graph_version_id=graph_id,
            approved_graph_exists=True,
        )
        evidence = Evidence(
            new_id(),
            owner.id,
            source.id,
            "queues",
            "artifact",
            "implement",
            "payload-hash",
            "Implemented a bounded queue",
            "learner-submit",
            timestamp,
        )
        uow.evidence.add_evidence(
            evidence,
            EvidencePayload(evidence.id, owner.id, source.id, "private body", "v1"),
        )
        uow.commit()
    return owner.id, source.id, target.id, evidence.id


def test_transfer_and_delete_are_conservative_exact_and_atomic(
    client, uow_factory: UnitOfWorkFactory, engine
) -> None:
    del client
    owner_id, source_id, target_id, evidence_id = _seed(uow_factory)
    with uow_factory() as uow:
        ref = transfer_evidence(
            uow,
            owner_id,
            source_goal_id=source_id,
            source_evidence_id=evidence_id,
            target_goal_id=target_id,
            classification=TransferClassification.PARTIAL,
            rationale="Useful experience, but the target bar is higher.",
            recommended_depth="Implementation",
        )
        uow.commit()

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM evidence")) == 1
        assert connection.scalar(text("SELECT count(*) FROM evidence_payloads")) == 1
        assert (
            connection.scalar(
                text("SELECT classification FROM learning_states WHERE id=:id"),
                {"id": ref.learning_state_id},
            )
            == "partial"
        )

    with uow_factory() as uow:
        before_evidence = uow.evidence.get_evidence(owner_id, source_id, evidence_id)
        impact = create_delete_preflight(uow, owner_id, source_id)
        uow.commit()
    assert impact.evidence_ids == (evidence_id,)
    assert impact.learning_state_ids == (ref.learning_state_id,)

    with uow_factory() as uow:
        realized = delete_goal(uow, owner_id, source_id, impact.snapshot_id)
        uow.commit()
    assert realized == impact

    with uow_factory() as uow:
        assert (
            uow.evidence.get_evidence(owner_id, source_id, evidence_id)
            == before_evidence
        )
        assert uow.evidence.get_payload(owner_id, source_id, evidence_id) is None
        assert [
            item.evidence_id
            for item in uow.evidence.list_tombstones(owner_id, source_id)
        ] == [evidence_id]
        state = uow.roadmap.get_learning_state_for_topic(owner_id, target_id, "queues")
        assert state is not None and state.classification.value == "unverified"
        assert state.origin == "tombstoned-transfer"
        assert uow.profiles_goals.get_goal(owner_id, source_id) is None
        lifecycle_goal = uow.profiles_goals.get_goal_for_lifecycle(owner_id, source_id)
        assert (
            lifecycle_goal is not None and lifecycle_goal.status.value == "tombstoned"
        )
        delete_audits = [
            event
            for event in uow.audit.list_for_owner(owner_id)
            if event.action == "deleted" and event.entity_id == source_id
        ]
        assert len(delete_audits) == 1


def test_delete_failure_rolls_back_tombstone_payload_and_downgrade(
    client, uow_factory: UnitOfWorkFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    del client
    owner_id, source_id, target_id, evidence_id = _seed(uow_factory)
    with uow_factory() as uow:
        transfer_evidence(
            uow,
            owner_id,
            source_goal_id=source_id,
            source_evidence_id=evidence_id,
            target_goal_id=target_id,
            classification=TransferClassification.LIKELY_KNOWN,
            rationale="Prior evidence applies conservatively.",
            recommended_depth="Essential",
        )
        impact = create_delete_preflight(uow, owner_id, source_id)
        uow.commit()

    with uow_factory() as uow:
        original = SqlAlchemyRoadmapRepository.downgrade_transfer_dependents

        def fail_after_payload(repository, *args, **kwargs):
            original(repository, *args, **kwargs)
            raise RuntimeError("forced mid-transaction failure")

        monkeypatch.setattr(
            SqlAlchemyRoadmapRepository,
            "downgrade_transfer_dependents",
            fail_after_payload,
        )
        with pytest.raises(RuntimeError, match="forced mid-transaction"):
            delete_goal(uow, owner_id, source_id, impact.snapshot_id)

    with uow_factory() as uow:
        assert uow.evidence.get_payload(owner_id, source_id, evidence_id) is not None
        assert uow.evidence.list_tombstones(owner_id, source_id) == ()
        state = uow.roadmap.get_learning_state_for_topic(owner_id, target_id, "queues")
        assert state is not None and state.classification.value == "likely-known"
        assert uow.profiles_goals.get_goal(owner_id, source_id) is not None


def test_delete_rejects_a_stale_impact_snapshot(
    client, uow_factory: UnitOfWorkFactory
) -> None:
    del client
    owner_id, source_id, target_id, evidence_id = _seed(uow_factory)
    with uow_factory() as uow:
        impact = create_delete_preflight(uow, owner_id, source_id)
        uow.commit()

    with uow_factory() as uow:
        transfer_evidence(
            uow,
            owner_id,
            source_goal_id=source_id,
            source_evidence_id=evidence_id,
            target_goal_id=target_id,
            classification=TransferClassification.PARTIAL,
            rationale="Prior evidence is only partially transferable.",
            recommended_depth="Implementation",
        )
        uow.commit()

    with (
        uow_factory() as uow,
        pytest.raises(ConflictError, match="impact changed after preflight"),
    ):
        delete_goal(uow, owner_id, source_id, impact.snapshot_id)

    with uow_factory() as uow:
        assert uow.evidence.get_payload(owner_id, source_id, evidence_id) is not None
        assert uow.evidence.list_tombstones(owner_id, source_id) == ()
        assert uow.profiles_goals.get_goal(owner_id, source_id) is not None


def test_delete_api_replays_the_same_snapshot_and_effect(
    client, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id, source_id, target_id, evidence_id = _seed(uow_factory)
    with uow_factory() as uow:
        transfer_evidence(
            uow,
            owner_id,
            source_goal_id=source_id,
            source_evidence_id=evidence_id,
            target_goal_id=target_id,
            classification=TransferClassification.PARTIAL,
            rationale="Prior evidence is only partially transferable.",
            recommended_depth="Implementation",
        )
        uow.commit()

    preflight_headers = {"Idempotency-Key": "delete-preflight"}
    preflight = client.post(
        f"/api/v1/goals/{source_id}/delete-preflight", headers=preflight_headers
    )
    assert preflight.status_code == 200, preflight.text
    replay = client.post(
        f"/api/v1/goals/{source_id}/delete-preflight", headers=preflight_headers
    )
    assert replay.status_code == 200
    assert replay.json() == preflight.json()

    delete_headers = {"Idempotency-Key": "delete-confirm"}
    body = {"snapshot_id": preflight.json()["snapshot_id"]}
    deleted = client.post(
        f"/api/v1/goals/{source_id}/delete", headers=delete_headers, json=body
    )
    assert deleted.status_code == 200, deleted.text
    delete_replay = client.post(
        f"/api/v1/goals/{source_id}/delete", headers=delete_headers, json=body
    )
    assert delete_replay.status_code == 200
    assert delete_replay.json() == deleted.json() == preflight.json()

    with uow_factory() as uow:
        delete_audits = [
            event
            for event in uow.audit.list_for_owner(owner_id)
            if event.action == "deleted" and event.entity_id == source_id
        ]
        assert len(delete_audits) == 1

"""Focused IDK-404 tutor and explicit source-retrieval wiring."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from tests.integration.test_generated_content_api import _goal, _source
from tests.job_assertions import wait_for_job
from tests.provider_fakes import install_provider_port_fake
from yuno.modules.provenance.domain import (
    SourceAvailability,
    SourceRetrievalRequest,
    SourceRetrievalResult,
)
from yuno.modules.provider.domain import (
    ProviderName,
    ProviderResult,
    ProviderResultState,
)
from yuno.shared.domain.hashing import hash_payload


@dataclass
class FakeProviderPort:
    provider: str = ProviderName.CODEX.value
    adapter_version: str = "fixture-provider-v1"
    contract_version: str = "final-json-v1"
    calls: int = 0

    def invoke(self, request, validator, *, on_spawn, cancelled):
        self.calls += 1
        assert request.purpose == "tutor-turn"
        assert request.context["conversation"][-1] == (
            "learner",
            request.context["message"],
        )
        payload = validator.validate(
            {"body": f"Tutor reply to: {request.context['message']}"}
        )
        return ProviderResult(
            state=ProviderResultState.SUCCEEDED,
            provider=ProviderName.CODEX,
            model="fixture-model",
            contract_version=self.contract_version,
            schema_version=request.output_schema_version,
            payload=payload,
            result_hash=hash_payload(payload),
            timestamp="2026-08-13T10:00:00.000000Z",
        )


@dataclass
class FakeRetriever:
    calls: int = 0
    fail: bool = False

    def retrieve(
        self,
        request: SourceRetrievalRequest,
        *,
        cancelled=lambda: False,
    ) -> SourceRetrievalResult:
        self.calls += 1
        assert not cancelled()
        if self.fail:
            raise RuntimeError("synthetic retrieval failure")
        return SourceRetrievalResult(
            content_ref=f"secure:source:{request.source_id}:v1",
            content_hash=hash_payload({"source_id": request.source_id, "version": 1}),
            retrieved_at="2026-08-13T10:00:00.000000Z",
            version_label="fixture-v1",
        )


def test_topic_get_is_read_only_and_explicit_tutor_turn_persists_reply(
    client, uow_factory, engine
):
    goal_id, topic_id = _goal(client, uow_factory, suffix="tutor-conversation")
    provider = FakeProviderPort()
    install_provider_port_fake(client, provider)

    empty = client.get(f"/api/v1/goals/{goal_id}/topics/{topic_id}/conversation")
    assert empty.status_code == 200
    assert empty.json() == []
    assert provider.calls == 0

    blocked = client.post(
        f"/api/v1/goals/{goal_id}/topics/{topic_id}/conversation",
        headers={"Idempotency-Key": "tutor-turn-blocked"},
        json={"message": "Explain the failure window."},
    )
    assert blocked.status_code == 412
    assert (
        client.get(f"/api/v1/goals/{goal_id}/topics/{topic_id}/conversation").json()
        == []
    )

    accepted = client.post(
        "/api/v1/disclosures/provider-generation/accept",
        json={"disclosure_version": "provider-network-v1"},
    )
    assert accepted.status_code == 200
    sent = client.post(
        f"/api/v1/goals/{goal_id}/topics/{topic_id}/conversation",
        headers={"Idempotency-Key": "tutor-turn-live"},
        json={"message": "Explain the failure window."},
    )
    assert sent.status_code == 202, sent.text
    wait_for_job(client, sent, "succeeded")
    turns = client.get(f"/api/v1/goals/{goal_id}/topics/{topic_id}/conversation").json()
    assert [(turn["role"], turn["body"]) for turn in turns] == [
        ("learner", "Explain the failure window."),
        ("tutor", "Tutor reply to: Explain the failure window."),
    ]
    assert provider.calls == 1
    with engine.connect() as connection:
        provider_request = (
            connection.execute(
                text(
                    "SELECT purpose, lifecycle, job_id FROM provider_requests "
                    "WHERE job_id = :job_id"
                ),
                {"job_id": sent.json()["job_id"]},
            )
            .mappings()
            .one()
        )
    assert dict(provider_request) == {
        "purpose": "tutor-turn",
        "lifecycle": "succeeded",
        "job_id": sent.json()["job_id"],
    }

    client.post(
        "/api/v1/disclosures/provider-generation/revoke",
        params={"disclosure_version": "provider-network-v1"},
    )
    replay = client.post(
        f"/api/v1/goals/{goal_id}/topics/{topic_id}/conversation",
        headers={"Idempotency-Key": "tutor-turn-live"},
        json={"message": "Explain the failure window."},
    )
    assert replay.status_code == 202
    assert replay.json()["job_id"] == sent.json()["job_id"]
    assert provider.calls == 1


def test_source_retrieval_requires_explicit_post_and_preserves_prior_state_on_failure(
    client, uow_factory
):
    available_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="retrievable"
    )
    withdrawn_id = _source(
        uow_factory, availability=SourceAvailability.WITHDRAWN, suffix="withdrawn"
    )
    retriever = FakeRetriever()
    client.app.state.source_retrieval_adapter = retriever

    assert client.get(f"/api/v1/sources/{available_id}").status_code == 200
    snapshots = client.get(f"/api/v1/sources/{available_id}/snapshots")
    assert snapshots.status_code == 200
    assert snapshots.json() == []
    assert retriever.calls == 0

    withdrawn = client.post(
        f"/api/v1/sources/{withdrawn_id}/retrieve",
        headers={"Idempotency-Key": "withdrawn-retrieval"},
    )
    assert withdrawn.status_code == 409
    assert retriever.calls == 0

    accepted = client.post(
        "/api/v1/disclosures/source-retrieval/accept",
        json={"disclosure_version": "source-network-v1"},
    )
    assert accepted.status_code == 200
    started = client.post(
        f"/api/v1/sources/{available_id}/retrieve",
        headers={"Idempotency-Key": "source-retrieval-live"},
    )
    assert started.status_code == 202, started.text
    wait_for_job(client, started, "succeeded")
    saved = client.get(f"/api/v1/sources/{available_id}/snapshots").json()
    assert len(saved) == 1
    assert saved[0]["content_ref"] == f"secure:source:{available_id}:v1"
    assert retriever.calls == 1

    retriever.fail = True
    failed = client.post(
        f"/api/v1/sources/{available_id}/retrieve",
        headers={"Idempotency-Key": "source-retrieval-failed"},
    )
    assert failed.status_code == 202
    wait_for_job(client, failed, "failed")
    after = client.get(f"/api/v1/sources/{available_id}/snapshots").json()
    # The append-only snapshot log now also records the failed attempt (newest
    # first), but the prior succeeded snapshot is preserved untouched.
    assert len(after) == 2
    assert after[1] == saved[0]
    assert after[0]["source_id"] == available_id
    assert after[0]["status"] == "failed"
    assert after[0]["content_ref"] == f"source-retrieval:failed:{after[0]['id']}"
    # A single failed attempt does not flip availability; IDK-003 §8 requires
    # 3 consecutive failures spanning >=72h before the source goes unavailable.
    assert (
        client.get(f"/api/v1/sources/{available_id}").json()["availability_status"]
        == "available"
    )

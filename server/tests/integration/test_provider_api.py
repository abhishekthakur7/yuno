from __future__ import annotations

from sqlalchemy import text

from yuno.modules.provider.domain import (
    ProviderFailureClassification,
    ProviderInput,
    ProviderName,
    ProviderResult,
    ProviderResultState,
    QuarantineDetails,
)
from yuno.modules.provider.service import enqueue_with_disclosure, execute_provider
from yuno.shared.application.jobs import JobRef, JobRequest, JobStatus
from yuno.shared.domain.errors import UnavailableError


class CapturingDispatcher:
    def __init__(self) -> None:
        self.requests = []

    def enqueue(self, request):
        self.requests.append(request)
        return JobRef(
            "captured-job", request.kind, JobStatus.QUEUED, "2999-01-01T00:00:00Z"
        )


class QuarantiningAdapter:
    provider = ProviderName.CODEX.value
    adapter_version = "test-adapter-v1"
    contract_version = "final-json-v1"

    def invoke(self, request, validator, *, on_spawn, cancelled):
        on_spawn(501, 501, "501:start")
        return ProviderResult(
            state=ProviderResultState.QUARANTINED,
            provider=ProviderName.CODEX,
            model="test-model",
            contract_version=self.contract_version,
            schema_version=request.output_schema_version,
            payload=None,
            result_hash=None,
            failure_classification=ProviderFailureClassification.SCHEMA_INVALID,
            retryable=True,
            quarantine=QuarantineDetails(
                raw_output_ref="secure-provider-output:invalid",
                raw_output_hash="invalid-output-hash",
                validation_errors=("answer:missing",),
            ),
        )


class UnavailableAdapter:
    provider = ProviderName.CODEX.value
    adapter_version = "unavailable"
    contract_version = "unavailable"

    def invoke(self, *_args, **_kwargs):
        raise UnavailableError("Provider configuration is unavailable.")


def _provider_execution_context(client):
    accepted = client.post(
        "/api/v1/disclosures/provider-generation/accept",
        json={"disclosure_version": "provider-network-v1"},
    )
    assert accepted.status_code == 200
    with client.app.state.uow_factory() as uow:
        owner_id = uow.owners.get_local_owner().id
    job = client.app.state.dispatcher.enqueue(
        JobRequest("parse_import", owner_id, {"import_id": "provider-test-job"})
    )
    return owner_id, job, accepted.json()["id"]


def test_capabilities_fail_closed_and_disclosure_lifecycle(client) -> None:
    capabilities = client.get("/api/v1/provider-capabilities")
    assert capabilities.status_code == 200
    assert {item["provider"] for item in capabilities.json()} == {"codex", "claude"}
    assert {item["state"] for item in capabilities.json()} == {
        "authentication-unavailable"
    }
    assert all(item["adapter_version"] is None for item in capabilities.json())
    assert all(item["contract_version"] is None for item in capabilities.json())
    assert all(item["reason"] for item in capabilities.json())
    assert all(item["recovery_action"] for item in capabilities.json())

    accepted = client.post(
        "/api/v1/disclosures/provider-generation/accept",
        json={
            "disclosure_version": "provider-network-v1",
        },
    )
    assert accepted.status_code == 200
    listed = client.get("/api/v1/disclosures").json()
    assert (
        next(item for item in listed if item["category"] == "provider-generation")
        == accepted.json()
    )
    assert (
        next(item for item in listed if item["category"] == "source-retrieval")[
            "accepted_at"
        ]
        is None
    )
    revoked = client.post(
        "/api/v1/disclosures/provider-generation/revoke",
        params={"disclosure_version": "provider-network-v1"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    reaccepted = client.post(
        "/api/v1/disclosures/provider-generation/accept",
        json={"disclosure_version": "provider-network-v1"},
    )
    assert reaccepted.status_code == 200
    assert reaccepted.json()["revoked_at"] is None
    assert reaccepted.json()["id"] == accepted.json()["id"]


def test_capability_reads_use_cache_and_refresh_is_explicit(client) -> None:
    registry = client.app.state.provider_registry
    calls = {provider: 0 for provider in ProviderName}
    original = dict(registry._discoveries)  # noqa: SLF001

    for provider, discovery in original.items():

        def counted(discovery=discovery, provider=provider):
            calls[provider] += 1
            return discovery()

        registry._discoveries[provider] = counted  # noqa: SLF001

    assert client.get("/api/v1/provider-capabilities").status_code == 200
    assert calls == {provider: 0 for provider in ProviderName}
    assert client.get("/api/v1/provider-capabilities?refresh=true").status_code == 200
    assert calls == {provider: 1 for provider in ProviderName}


def test_disclosure_definition_is_server_owned_and_precedes_enqueue(client) -> None:
    rejected = client.post(
        "/api/v1/disclosures/provider-generation/accept",
        json={"disclosure_version": "caller-invented-v9"},
    )
    assert rejected.status_code == 422

    accepted = client.post(
        "/api/v1/disclosures/provider-generation/accept",
        json={"disclosure_version": "provider-network-v1"},
    )
    body = accepted.json()
    assert accepted.status_code == 200
    assert body["operation"] == "Provider-backed generation and evaluation"
    assert "credentials" not in body["data_categories"]

    dispatcher = CapturingDispatcher()
    with client.app.state.uow_factory() as uow:
        owner_id = uow.owners.get_local_owner().id
        job = enqueue_with_disclosure(
            uow,
            dispatcher,
            JobRequest("provider-test", owner_id, {}),
            category="provider-generation",
            disclosure_version="provider-network-v1",
        )

    assert dispatcher.requests[0].disclosure_ref == body["id"]
    assert body["accepted_at"] < job.enqueued_at


def test_invalid_provider_output_is_quarantined_and_never_published(
    client, engine
) -> None:
    owner_id, job, disclosure_id = _provider_execution_context(client)

    result = execute_provider(
        client.app.state.uow_factory,
        QuarantiningAdapter(),
        ProviderInput(
            owner_id=owner_id,
            goal_id=None,
            job_id=job.job_id,
            purpose="evaluation",
            context={"answer_ref": "answer-1"},
            context_ref_hash="context-hash",
            disclosure_id=disclosure_id,
            output_schema_version="evaluation-v1",
        ),
        validator=None,
    )

    assert result.state is ProviderResultState.QUARANTINED
    assert result.payload is None
    assert result.result_hash is None
    assert result.quarantine_id is not None
    with engine.connect() as connection:
        quarantine = (
            connection.execute(
                text(
                    "SELECT b.raw_output_ref, q.raw_output_hash, q.expected_schema_version "
                    "FROM schema_quarantines q JOIN schema_quarantine_bodies b "
                    "ON b.quarantine_id=q.id WHERE q.id = :id"
                ),
                {"id": result.quarantine_id},
            )
            .mappings()
            .one()
        )
        assert dict(quarantine) == {
            "raw_output_ref": "secure-provider-output:invalid",
            "raw_output_hash": "invalid-output-hash",
            "expected_schema_version": "evaluation-v1",
        }
        for table in ("job_results", "generated_artifacts", "assessments", "evidence"):
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def test_unavailable_provider_is_a_recoverable_configuration_failure(client) -> None:
    owner_id, job, disclosure_id = _provider_execution_context(client)

    result = execute_provider(
        client.app.state.uow_factory,
        UnavailableAdapter(),
        ProviderInput(
            owner_id=owner_id,
            goal_id=None,
            job_id=job.job_id,
            purpose="evaluation",
            context={"answer_ref": "answer-1"},
            context_ref_hash="context-hash",
            disclosure_id=disclosure_id,
            output_schema_version="evaluation-v1",
        ),
        validator=None,
    )

    assert result.state is ProviderResultState.FAILED
    assert result.failure_classification is (
        ProviderFailureClassification.AUTHENTICATION_UNAVAILABLE
    )
    assert result.retryable is True

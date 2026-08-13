"""Deterministic domain fakes exposed through the real ProviderPort boundary."""

from __future__ import annotations

import json
from dataclasses import asdict
from types import SimpleNamespace

from yuno.modules.evidence_evaluation.domain import EvaluationRequest
from yuno.modules.learning_content.domain import GenerateRequest
from yuno.modules.provider.domain import (
    ProviderCapability,
    ProviderCapabilityState,
    ProviderName,
    ProviderResult,
    ProviderResultState,
)
from yuno.shared.domain.hashing import hash_payload


class DomainFakeProviderPort:
    adapter_version = "domain-fake-v1"
    contract_version = "final-json-v1"

    def __init__(
        self, adapter, provider_name: ProviderName = ProviderName.CODEX
    ) -> None:
        self.adapter = adapter
        self.provider_name = provider_name

    @property
    def provider(self):
        return self.provider_name.value

    @property
    def model(self):
        return getattr(self.adapter, "model", None)

    def invoke(self, request, validator, *, on_spawn, cancelled):
        on_spawn(999_001, 999_001, "999001:fixture")
        if request.purpose == "topic-generation":
            result = self.adapter.generate(GenerateRequest(**request.context))
            if result.schema_version != request.output_schema_version:
                raise ValueError("fixture returned an unsupported schema")
            payload = {
                "body": result.body,
                "provenance_refs": list(result.provenance_refs),
                "warnings": list(result.warnings),
                "claims": [asdict(item) for item in result.claims],
            }
            payload = json.loads(json.dumps(payload))
            model, timestamp = result.model, result.generated_at
        elif request.purpose == "evaluation":
            result = self.adapter.evaluate(EvaluationRequest(**request.context))
            payload = json.loads(json.dumps(asdict(result)))
            model, timestamp = "fixture-evaluator", None
        elif request.purpose == "mock-next-turn":
            payload = {
                "question": self.adapter.next_question(_namespace(request.context))
            }
            model, timestamp = "fixture-interviewer", None
        else:
            raise AssertionError(f"Unexpected provider purpose {request.purpose!r}")
        validated = validator.validate(payload)
        return ProviderResult(
            ProviderResultState.SUCCEEDED,
            self.provider_name,
            model,
            self.contract_version,
            request.output_schema_version,
            validated,
            hash_payload(validated),
            timestamp=timestamp,
        )


def install_provider_fake(client, adapter) -> None:
    install_provider_port_fake(client, DomainFakeProviderPort(adapter))


def configure_provider_port_fake(
    client, provider, name: ProviderName = ProviderName.CODEX
) -> None:
    registry = client.app.state.provider_registry
    registry._discoveries[name] = lambda: (  # noqa: SLF001
        ProviderCapability(
            name,
            ProviderCapabilityState.CONFIGURED,
            model=getattr(provider, "model", "fixture-model"),
            adapter_version=provider.adapter_version,
            contract_version=provider.contract_version,
        ),
        provider,
    )
    registry.refresh()


def install_provider_port_fake(client, provider) -> None:
    configure_provider_port_fake(client, provider)
    settings = client.get("/api/v1/settings")
    assert settings.status_code == 200
    selected = client.patch(
        "/api/v1/settings",
        headers={"If-Match": str(settings.json()["row_version"])},
        json={"provider_selection": "codex"},
    )
    assert selected.status_code == 200, selected.text


def accept_provider_disclosure(client) -> None:
    response = client.post(
        "/api/v1/disclosures/provider-generation/accept",
        json={"disclosure_version": "provider-network-v1"},
    )
    assert response.status_code == 200, response.text


def _namespace(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _namespace(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_namespace(item) for item in value]
    return value

"""Public API and concurrency coverage for IDK-207 generated content."""

from __future__ import annotations

import threading
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from tests.job_assertions import wait_for_job
from tests.provider_fakes import (
    accept_provider_disclosure,
    install_provider_fake,
    install_provider_port_fake,
)
from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    ContentRevision,
    EditorialApproval,
    Topic,
    TopicIdentity,
)
from yuno.modules.imports.domain import TopicImportHash
from yuno.modules.learning_content.domain import (
    GENERATION_SCHEMA_VERSION,
    GeneratedCitation,
    GeneratedClaim,
    GenerateRequest,
    GenerateResult,
)
from yuno.modules.provenance.domain import Source, SourceAvailability
from yuno.modules.provider.domain import (
    ProviderName,
    ProviderResult,
    ProviderResultState,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.hashing import hash_payload


@pytest.fixture(autouse=True)
def accepted_provider_disclosure(client):
    accept_provider_disclosure(client)


def test_live_provider_wiring_enqueues_claims_records_and_publishes(
    client, engine, uow_factory
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="provider-wiring")

    class ValidatingProvider:
        provider = "codex"
        adapter_version = "fixture-provider-v1"
        contract_version = "final-json-v1"

        def invoke(self, request, validator, *, on_spawn, cancelled):
            on_spawn(9001, 9001, "9001:fixture")
            payload = validator.validate(
                {
                    "body": "Validated provider-backed lesson.",
                    "provenance_refs": [],
                    "warnings": [],
                }
            )
            return ProviderResult(
                ProviderResultState.SUCCEEDED,
                ProviderName.CODEX,
                "fixture-model",
                self.contract_version,
                request.output_schema_version,
                payload,
                hash_payload(payload),
                timestamp="2026-08-14T12:00:00Z",
            )

    install_provider_port_fake(client, ValidatingProvider())
    response = _generate(client, goal_id, topic_id, key="provider-wiring")
    assert response.status_code == 202
    wait_for_job(client, response, "succeeded")
    layer = _essential_layer(client, goal_id, topic_id)
    assert layer["markdown"] == "Validated provider-backed lesson."
    with engine.connect() as connection:
        provider_request = connection.execute(
            text(
                "SELECT provider, lifecycle, context_ref_hash, disclosure_id FROM provider_requests"
            )
        ).one()
        assert provider_request.provider == "codex"
        assert provider_request.lifecycle == "succeeded"
        assert provider_request.context_ref_hash
        assert provider_request.disclosure_id


def test_generation_without_disclosure_does_not_reserve_attempt_or_job(
    client, engine, uow_factory
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="disclosure-gate")
    revoked = client.post(
        "/api/v1/disclosures/provider-generation/revoke",
        params={"disclosure_version": "provider-network-v1"},
    )
    assert revoked.status_code == 200
    response = _generate(client, goal_id, topic_id, key="disclosure-gate")
    assert response.status_code == 412
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM artifact_generation_attempts"))
            == 0
        )
        assert connection.scalar(text("SELECT count(*) FROM jobs")) == 0


def test_generation_without_selected_provider_is_fail_closed_before_reservation(
    client, engine, uow_factory
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="no-provider")
    response = _generate(client, goal_id, topic_id, key="no-provider")
    assert response.status_code == 503
    assert response.json()["current_state"] == "provider-not-selected"
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM artifact_generation_attempts"))
            == 0
        )
        assert connection.scalar(text("SELECT count(*) FROM jobs")) == 0


from yuno.shared.domain.ids import new_id


def _goal(
    client: TestClient, uow_factory: UnitOfWorkFactory, *, suffix: str
) -> tuple[str, str]:
    graph_id = new_id()
    topic_id = f"generated-topic-{suffix}"
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
                f"generated-{suffix}-{graph_id}",
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
                f"Generated topic {suffix}",
                "backend",
                ("fixture",),
                "senior",
                "implement",
                "essential",
                0,
                1,
            )
        )
        uow.canonical.add_content_revision(
            ContentRevision(
                f"content-revision-{suffix}",
                graph_id,
                topic_id,
                "Essential",
                "layer",
                "published",
                "inline:Authored fallback",
                f"authored-hash-{suffix}",
                None,
                owner.id,
                None,
                timestamp,
            )
        )
        uow.canonical.record_approval(
            EditorialApproval(
                new_id(),
                graph_id,
                owner.id,
                "designated_editorial_approver",
                "IDK-207 fixture",
                timestamp,
            )
        )
        uow.commit()
    response = client.post(
        "/api/v1/goals",
        headers={"Idempotency-Key": f"generated-goal-{suffix}"},
        json={
            "name": f"Generated {suffix}",
            "path": "learn",
            "subject": "backend",
            "target_level": "Senior",
            "target_capability": "implement",
            "graph_version_id": graph_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], topic_id


def _source(
    uow_factory: UnitOfWorkFactory, *, availability: SourceAvailability, suffix: str
) -> str:
    timestamp = "2026-08-01T00:00:00.000000Z"
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        source = Source(
            new_id(),
            owner.id,
            "fixture",
            "documentation",
            f"Source {suffix}",
            "Fixture publisher",
            f"https://example.invalid/{suffix}",
            "fixture-approved",
            availability,
            timestamp,
            timestamp,
        )
        uow.provenance.add_source(source)
        uow.commit()
    return source.id


@dataclass
class FakeGenerationAdapter:
    body: str
    source_id: str
    provider: str = "fixture-provider"
    model: str = "fixture-model-v1"
    fail: bool = False
    calls: int = 0

    def generate(self, request: GenerateRequest) -> GenerateResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("fixture generation failed")
        return GenerateResult(
            body=self.body,
            provider=self.provider,
            model=self.model,
            contract_version="fixture-provider-contract-v1",
            schema_version=GENERATION_SCHEMA_VERSION,
            generated_at="2026-08-12T12:00:00.000000Z",
            claims=(
                GeneratedClaim(
                    "A sensitive factual fixture claim.",
                    "fact",
                    sensitive=True,
                    citations=(
                        GeneratedCitation(
                            self.source_id, None, "section-1", "supports", None
                        ),
                    ),
                ),
                GeneratedClaim("Routine explanatory content.", "routine"),
            ),
        )


def _generate(client: TestClient, goal_id: str, topic_id: str, *, key: str):
    return client.post(
        f"/api/v1/goals/{goal_id}/topics/{topic_id}/generate",
        params={"layer": "Essential"},
        headers={"Idempotency-Key": key},
    )


def _change_imports_hash(
    uow_factory: UnitOfWorkFactory, goal_id: str, topic_id: str, imports_hash: str
) -> None:
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
        assert owner is not None
        goal = uow.profiles_goals.get_goal(owner.id, goal_id)
        assert goal is not None
        uow.imports.upsert_topic_hash(
            TopicImportHash(
                owner.id,
                goal_id,
                goal.graph_version_id,
                topic_id,
                imports_hash,
                "2026-08-13T00:00:00.000000Z",
            )
        )
        uow.commit()


def _essential_layer(
    client: TestClient, goal_id: str, topic_id: str
) -> dict[str, object]:
    response = client.get(f"/api/v1/goals/{goal_id}/topics/{topic_id}/layers/Essential")
    assert response.status_code == 200, response.text
    return response.json()


def test_ready_cache_hit_and_provenance_apis_retain_unavailable_sources(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="ready-hit")
    source_id = _source(
        uow_factory, availability=SourceAvailability.WITHDRAWN, suffix="withdrawn"
    )
    adapter = FakeGenerationAdapter("First immutable visible body.", source_id)
    install_provider_fake(client, adapter)

    first = _generate(client, goal_id, topic_id, key="generate-ready-1")
    assert first.status_code == 202, first.text
    wait_for_job(client, first)
    assert adapter.calls == 1
    completion_replay = _generate(client, goal_id, topic_id, key="generate-ready-1")
    assert completion_replay.status_code == 202
    assert completion_replay.json()["job_id"] == first.json()["job_id"]
    assert completion_replay.json()["deduplicated"] is True
    assert adapter.calls == 1
    ready = _essential_layer(client, goal_id, topic_id)
    assert ready["state"] == "ready"
    assert ready["markdown"] == adapter.body
    assert ready["markdown_hash"]
    artifact_id = ready["artifact_id"]

    cache_hit = _generate(client, goal_id, topic_id, key="generate-ready-2")
    assert cache_hit.status_code == 202
    assert cache_hit.json()["job_id"] == first.json()["job_id"]
    assert cache_hit.json()["deduplicated"] is True
    assert adapter.calls == 1

    provenance = client.get(f"/api/v1/artifacts/{artifact_id}/provenance")
    assert provenance.status_code == 200, provenance.text
    payload = provenance.json()
    assert payload["artifact_id"] == artifact_id
    assert payload["stale"] is False
    assert payload["baked_snapshot"]["provider"] == "codex"
    assert payload["baked_snapshot"]["model"] == adapter.model
    assert len(payload["claims"]) == 2
    sensitive = next(claim for claim in payload["claims"] if claim["sensitive"])
    routine = next(
        claim for claim in payload["claims"] if claim["claim_type"] == "routine"
    )
    assert sensitive["citations"][0]["source"]["availability_status"] == "withdrawn"
    assert routine["citations"] == []
    claim = client.get(f"/api/v1/claims/{sensitive['id']}")
    assert claim.status_code == 200
    assert claim.json() == sensitive

    sources = client.get("/api/v1/sources")
    assert sources.status_code == 200
    assert any(
        item["id"] == source_id and item["availability_status"] == "withdrawn"
        for item in sources.json()
    )
    assert (
        client.get(f"/api/v1/sources/{source_id}").json()["availability_status"]
        == "withdrawn"
    )

    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM generated_artifacts WHERE id=:id"),
                {"id": artifact_id},
            ).scalar_one()
            == 1
        )


def test_generation_idempotency_key_reuse_with_a_different_request_conflicts_without_orphan_rows(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="idempotency-conflict")
    source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="idem"
    )
    adapter = FakeGenerationAdapter("Idempotent body.", source_id)
    install_provider_fake(client, adapter)
    first = _generate(client, goal_id, topic_id, key="globally-reused-generation-key")
    assert first.status_code == 202

    conflict = client.post(
        f"/api/v1/goals/{goal_id}/topics/{topic_id}/generate",
        params={"layer": "Production"},
        headers={"Idempotency-Key": "globally-reused-generation-key"},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "idempotency_key_reused"
    wait_for_job(client, first)
    assert adapter.calls == 1
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM generated_artifacts")
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM artifact_generation_attempts")
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM learning_content_idempotency")
            ).scalar_one()
            == 1
        )


def test_personalization_and_provider_changes_surface_stale_without_swapping_body(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="stale")
    source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="stale"
    )
    adapter = FakeGenerationAdapter("Body baked before learner changes.", source_id)
    install_provider_fake(client, adapter)
    generated = _generate(client, goal_id, topic_id, key="generate-stale")
    assert generated.status_code == 202
    wait_for_job(client, generated)
    baseline = _essential_layer(client, goal_id, topic_id)
    artifact_id = baseline["artifact_id"]

    adapter.provider = "fixture-provider-v2"
    adapter.model = "fixture-model-v2"
    provider_stale = client.get(f"/api/v1/artifacts/{artifact_id}/provenance")
    assert provider_stale.status_code == 200
    assert provider_stale.json()["stale"] is True
    assert "personalization-snapshot-mismatch" in provider_stale.json()["stale_reasons"]
    provider_visible = _essential_layer(client, goal_id, topic_id)
    assert provider_visible["artifact_id"] == baseline["artifact_id"]
    assert provider_visible["markdown"] == baseline["markdown"]
    assert provider_visible["markdown_hash"] == baseline["markdown_hash"]

    adapter.provider = "fixture-provider"
    adapter.model = "fixture-model-v1"
    profile = client.get("/api/v1/profile").json()
    changed_profile = client.patch(
        "/api/v1/profile",
        headers={"If-Match": str(profile["profile_revision"])},
        json={"strengths": "New strength after generation"},
    )
    assert changed_profile.status_code == 200
    evidence = client.post(
        f"/api/v1/goals/{goal_id}/evidence",
        headers={"Idempotency-Key": "staleness-evidence"},
        json={
            "topic_stable_id": topic_id,
            "evidence_type": "fixture",
            "capability": "implement",
            "summary": "New evidence after generation",
            "origin": "test",
            "content": "new evidence",
            "content_version": "fixture-v1",
        },
    )
    assert evidence.status_code == 201
    stale = client.get(f"/api/v1/artifacts/{artifact_id}/provenance")
    assert stale.status_code == 200, stale.text
    assert stale.json()["stale"] is True
    assert "personalization-snapshot-mismatch" in stale.json()["stale_reasons"]
    current = _essential_layer(client, goal_id, topic_id)
    assert current["artifact_id"] == baseline["artifact_id"]
    assert current["markdown"] == baseline["markdown"]
    assert current["markdown_hash"] == baseline["markdown_hash"]


def test_correction_and_learning_state_changes_mark_stale_without_swapping_body(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="correction-stale")
    source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="correction"
    )
    adapter = FakeGenerationAdapter("Body baked before correction.", source_id)
    install_provider_fake(client, adapter)
    generated = _generate(client, goal_id, topic_id, key="generate-before-correction")
    assert generated.status_code == 202
    wait_for_job(client, generated)
    baseline = _essential_layer(client, goal_id, topic_id)

    correction = client.post(
        f"/api/v1/goals/{goal_id}/corrections",
        headers={"Idempotency-Key": "generated-content-correction"},
        json={
            "topic_stable_id": topic_id,
            "classification": "partial",
            "correction_type": "correction",
            "reason": "Learner corrected the inferred state",
        },
    )
    assert correction.status_code == 200, correction.text
    states = client.get(f"/api/v1/goals/{goal_id}/learning-states")
    assert states.status_code == 200
    assert any(item["topic_stable_id"] == topic_id for item in states.json())

    provenance = client.get(f"/api/v1/artifacts/{baseline['artifact_id']}/provenance")
    assert provenance.status_code == 200
    assert provenance.json()["stale"] is True
    assert "personalization-snapshot-mismatch" in provenance.json()["stale_reasons"]
    visible = _essential_layer(client, goal_id, topic_id)
    assert visible["artifact_id"] == baseline["artifact_id"]
    assert visible["markdown"] == baseline["markdown"]
    assert visible["markdown_hash"] == baseline["markdown_hash"]


def test_key_changing_generation_keeps_prior_body_visible_during_new_failure_and_provenance_survives(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="key-movement")
    source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="key-movement"
    )
    original_adapter = FakeGenerationAdapter("Prior ready body.", source_id)
    install_provider_fake(client, original_adapter)
    generated = _generate(client, goal_id, topic_id, key="old-key-generate")
    assert generated.status_code == 202
    wait_for_job(client, generated)
    prior = _essential_layer(client, goal_id, topic_id)
    prior_artifact_id = prior["artifact_id"]

    _change_imports_hash(uow_factory, goal_id, topic_id, "approved-imports-v2")
    entered = threading.Event()
    release = threading.Event()

    class BlockingFailureAdapter(FakeGenerationAdapter):
        def generate(self, request: GenerateRequest) -> GenerateResult:
            self.calls += 1
            entered.set()
            assert release.wait(timeout=5), "key-changing generation was never released"
            raise RuntimeError("new exact-key generation failed")

    failing = BlockingFailureAdapter("must never be visible", source_id)
    install_provider_fake(client, failing)
    responses: list[object] = []
    thread = threading.Thread(
        target=lambda: responses.append(
            _generate(client, goal_id, topic_id, key="new-key-generate")
        )
    )
    thread.start()
    try:
        assert entered.wait(timeout=5), "new exact-key generation never started"
        during = _essential_layer(client, goal_id, topic_id)
        assert during["state"] == "stale"
        assert during["stale_reason"] == "cache-key-changed"
        assert during["artifact_id"] == prior_artifact_id
        assert during["markdown"] == prior["markdown"]
        assert during["markdown_hash"] == prior["markdown_hash"]

        old_provenance = client.get(f"/api/v1/artifacts/{prior_artifact_id}/provenance")
        assert old_provenance.status_code == 200
        assert old_provenance.json()["stale"] is True
        assert "cache-key-changed" in old_provenance.json()["stale_reasons"]
    finally:
        release.set()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert responses[0].status_code == 202
    wait_for_job(client, responses[0], "failed")

    after = _essential_layer(client, goal_id, topic_id)
    assert after["state"] == "stale"
    assert after["stale_reason"] == "cache-key-changed"
    assert after["artifact_id"] == prior_artifact_id
    assert after["markdown"] == prior["markdown"]
    assert after["markdown_hash"] == prior["markdown_hash"]
    assert (
        client.get(f"/api/v1/artifacts/{prior_artifact_id}/provenance").status_code
        == 200
    )
    with engine.connect() as connection:
        slots = connection.execute(
            text(
                "SELECT imports_hash, state, body_hash FROM generated_artifacts "
                "WHERE goal_id=:goal ORDER BY created_at"
            ),
            {"goal": goal_id},
        ).all()
    assert len(slots) == 2
    assert slots[0].body_hash == prior["markdown_hash"]
    assert slots[1].state == "failed"
    assert slots[1].body_hash is None


def test_explicit_regeneration_swaps_only_after_success_and_failure_keeps_prior_body(
    client: TestClient,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="regenerate")
    source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="regen"
    )
    adapter = FakeGenerationAdapter("Original cached body.", source_id)
    install_provider_fake(client, adapter)
    generated = _generate(client, goal_id, topic_id, key="generate-original")
    assert generated.status_code == 202
    wait_for_job(client, generated)
    original = _essential_layer(client, goal_id, topic_id)

    adapter.body = "Explicitly regenerated body."
    succeeded = client.post(
        f"/api/v1/artifacts/{original['artifact_id']}/regenerate",
        headers={"Idempotency-Key": "regenerate-success"},
    )
    assert succeeded.status_code == 202
    wait_for_job(client, succeeded)
    regenerated = _essential_layer(client, goal_id, topic_id)
    assert regenerated["artifact_id"] == original["artifact_id"]
    assert regenerated["markdown"] == adapter.body
    assert regenerated["markdown_hash"] != original["markdown_hash"]

    adapter.fail = True
    failed = client.post(
        f"/api/v1/artifacts/{original['artifact_id']}/regenerate",
        headers={"Idempotency-Key": "regenerate-failure"},
    )
    assert failed.status_code == 202
    wait_for_job(client, failed, "failed")
    preserved = _essential_layer(client, goal_id, topic_id)
    assert preserved["artifact_id"] == regenerated["artifact_id"]
    assert preserved["markdown"] == regenerated["markdown"]
    assert preserved["markdown_hash"] == regenerated["markdown_hash"]
    assert preserved["generation"]["retryable"] is True


def test_two_concurrent_generate_calls_single_flight_to_one_persisted_attempt(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="concurrent")
    source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="concurrent"
    )
    entered = threading.Event()
    release = threading.Event()

    class BlockingAdapter(FakeGenerationAdapter):
        def generate(self, request: GenerateRequest) -> GenerateResult:
            entered.set()
            assert release.wait(timeout=5), "blocking adapter was never released"
            return super().generate(request)

    adapter = BlockingAdapter("Single-flight body.", source_id)
    install_provider_fake(client, adapter)
    results: list[object] = []
    first = threading.Thread(
        target=lambda: results.append(
            _generate(client, goal_id, topic_id, key="concurrent-a")
        )
    )
    first.start()
    try:
        assert entered.wait(timeout=5), "first generation never reached adapter"
        second = _generate(client, goal_id, topic_id, key="concurrent-b")
    finally:
        release.set()
        first.join(timeout=5)
    assert not first.is_alive()
    first_response = results[0]
    assert first_response.status_code == 202
    assert second.status_code == 202
    assert second.json()["job_id"] == first_response.json()["job_id"]
    assert second.json()["deduplicated"] is True
    wait_for_job(client, first_response)
    assert adapter.calls == 1

    first_replay = _generate(client, goal_id, topic_id, key="concurrent-a")
    joined_replay = _generate(client, goal_id, topic_id, key="concurrent-b")
    assert first_replay.status_code == joined_replay.status_code == 202
    assert first_replay.json()["job_id"] == first_response.json()["job_id"]
    assert joined_replay.json()["job_id"] == first_response.json()["job_id"]
    assert first_replay.json()["deduplicated"] is True
    assert joined_replay.json()["deduplicated"] is True
    assert adapter.calls == 1

    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM generated_artifacts")
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM learning_content_idempotency")
            ).scalar_one()
            == 2
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM artifact_generation_attempts")
            ).scalar_one()
            == 1
        )


def test_changing_an_included_layer_component_creates_a_distinct_cache_entry(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="included-key")
    source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="included-key"
    )
    adapter = FakeGenerationAdapter("Keyed body.", source_id)
    install_provider_fake(client, adapter)
    essential = _generate(client, goal_id, topic_id, key="included-essential")
    production = client.post(
        f"/api/v1/goals/{goal_id}/topics/{topic_id}/generate",
        params={"layer": "Production"},
        headers={"Idempotency-Key": "included-production"},
    )
    assert essential.status_code == production.status_code == 202
    assert essential.json()["job_id"] != production.json()["job_id"]
    wait_for_job(client, essential)
    wait_for_job(client, production)
    assert adapter.calls == 2
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT layer, cache_key_hash FROM generated_artifacts "
                "WHERE goal_id=:goal ORDER BY layer"
            ),
            {"goal": goal_id},
        ).all()
    assert len(rows) == 2
    assert len({row.cache_key_hash for row in rows}) == 2


def test_invalid_generation_result_rolls_back_artifact_snapshot_claims_and_citations(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="atomic-rollback")
    source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="rollback"
    )

    class MissingCitationAdapter(FakeGenerationAdapter):
        def generate(self, request: GenerateRequest) -> GenerateResult:
            self.calls += 1
            return GenerateResult(
                body="This body must never become visible.",
                provider=self.provider,
                model=self.model,
                contract_version="fixture-provider-contract-v1",
                schema_version=GENERATION_SCHEMA_VERSION,
                generated_at="2026-08-12T12:00:00.000000Z",
                claims=(
                    GeneratedClaim(
                        "Sensitive output missing its required citation.",
                        "fact",
                        sensitive=True,
                    ),
                ),
            )

    adapter = MissingCitationAdapter("unused", source_id)
    install_provider_fake(client, adapter)
    response = _generate(client, goal_id, topic_id, key="atomic-rollback")
    assert response.status_code == 202
    wait_for_job(client, response, "failed")
    layer = _essential_layer(client, goal_id, topic_id)
    assert layer["markdown"] is None
    assert layer["state"] in {"absent", "unavailable"}
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM artifact_provenance_snapshots")
            ).scalar_one()
            == 0
        )
        assert connection.execute(text("SELECT count(*) FROM claims")).scalar_one() == 0
        assert (
            connection.execute(text("SELECT count(*) FROM citations")).scalar_one() == 0
        )
        artifact = connection.execute(
            text(
                "SELECT a.state, b.body_ref, a.body_hash, a.current_snapshot_id "
                "FROM generated_artifacts a LEFT JOIN generated_artifact_bodies b "
                "ON b.artifact_id=a.id AND b.owner_id=a.owner_id"
            )
        ).one()
    assert artifact.state == "failed"
    assert artifact.body_ref is None
    assert artifact.body_hash is None
    assert artifact.current_snapshot_id is None


def test_schema_invalid_result_is_quarantined_and_never_replaces_prior_ready_content(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="schema-quarantine")
    source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="quarantine"
    )
    valid = FakeGenerationAdapter("Prior validated body.", source_id)
    install_provider_fake(client, valid)
    generated = _generate(client, goal_id, topic_id, key="quarantine-valid")
    assert generated.status_code == 202
    wait_for_job(client, generated)
    prior = _essential_layer(client, goal_id, topic_id)
    with engine.connect() as connection:
        prior_counts = {
            table: connection.execute(
                text(f"SELECT count(*) FROM {table}")
            ).scalar_one()
            for table in ("artifact_provenance_snapshots", "claims", "citations")
        }

    class WrongSchemaAdapter(FakeGenerationAdapter):
        def generate(self, request: GenerateRequest) -> GenerateResult:
            self.calls += 1
            return GenerateResult(
                body="Schema-invalid output must remain quarantined.",
                provider=self.provider,
                model=self.model,
                contract_version="fixture-provider-contract-v1",
                schema_version="unsupported-schema-v999",
                generated_at="2026-08-14T12:00:00.000000Z",
                claims=(GeneratedClaim("Routine but wrong schema.", "routine"),),
            )

    invalid = WrongSchemaAdapter("unused", source_id)
    install_provider_fake(client, invalid)
    response = client.post(
        f"/api/v1/artifacts/{prior['artifact_id']}/regenerate",
        headers={"Idempotency-Key": "quarantine-invalid"},
    )
    assert response.status_code == 202
    wait_for_job(client, response, "failed")

    visible = _essential_layer(client, goal_id, topic_id)
    assert visible["artifact_id"] == prior["artifact_id"]
    assert visible["markdown"] == prior["markdown"]
    assert visible["markdown_hash"] == prior["markdown_hash"]
    with engine.connect() as connection:
        attempt_status = connection.scalar(
            text(
                "SELECT status FROM artifact_generation_attempts WHERE status='failed'"
            )
        )
        after_counts = {
            table: connection.execute(
                text(f"SELECT count(*) FROM {table}")
            ).scalar_one()
            for table in ("artifact_provenance_snapshots", "claims", "citations")
        }
    assert attempt_status == "failed"
    assert after_counts == prior_counts


def test_provenance_and_regeneration_are_owner_scoped(
    client: TestClient,
) -> None:
    for path in (
        "/api/v1/artifacts/not-owned/provenance",
        "/api/v1/claims/not-owned",
        "/api/v1/sources/not-owned",
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"
    response = client.post(
        "/api/v1/artifacts/not-owned/regenerate",
        headers={"Idempotency-Key": "not-owned-regenerate"},
    )
    assert response.status_code == 404


def test_openapi_documents_async_generation_and_synchronous_provenance_reads(
    client: TestClient,
) -> None:
    paths = client.app.openapi()["paths"]
    for path in (
        "/api/v1/goals/{goal_id}/topics/{topic_id}/generate",
        "/api/v1/artifacts/{artifact_id}/regenerate",
    ):
        assert "202" in paths[path]["post"]["responses"]
    for path in (
        "/api/v1/sources",
        "/api/v1/sources/{source_id}",
        "/api/v1/claims/{claim_id}",
        "/api/v1/artifacts/{artifact_id}/provenance",
    ):
        responses = paths[path]["get"]["responses"]
        assert "200" in responses
        assert "202" not in responses


def test_required_claim_citations_and_immutable_provenance_are_database_enforced(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
) -> None:
    goal_id, topic_id = _goal(client, uow_factory, suffix="citation-guards")
    source_id = _source(
        uow_factory, availability=SourceAvailability.UNAVAILABLE, suffix="citation-a"
    )
    other_source_id = _source(
        uow_factory, availability=SourceAvailability.AVAILABLE, suffix="citation-b"
    )
    adapter = FakeGenerationAdapter("Citation guard fixture body.", source_id)
    install_provider_fake(client, adapter)
    generated = _generate(client, goal_id, topic_id, key="citation-guard-generation")
    assert generated.status_code == 202
    wait_for_job(client, generated)
    layer = _essential_layer(client, goal_id, topic_id)
    timestamp = "2026-08-12T12:00:00.000000Z"
    with engine.connect() as connection:
        owner_id = connection.execute(text("SELECT id FROM owners")).scalar_one()
        snapshot_id = connection.execute(
            text("SELECT current_snapshot_id FROM generated_artifacts WHERE id=:id"),
            {"id": layer["artifact_id"]},
        ).scalar_one()

    def claim_values(
        claim_id: str, claim_type: str, sensitive: int, status: str
    ) -> dict[str, object]:
        return {
            "id": claim_id,
            "owner": owner_id,
            "goal": goal_id,
            "artifact": layer["artifact_id"],
            "snapshot": snapshot_id,
            "text": f"{claim_type} claim {claim_id}",
            "hash": hash_payload(f"{claim_type} claim {claim_id}"),
            "type": claim_type,
            "sensitive": sensitive,
            "status": status,
        }

    insert_claim = text(
        "INSERT INTO claims "
        "(id,owner_id,goal_id,content_revision_id,generated_artifact_id,snapshot_id,"
        "claim_hash,claim_type,sensitive,status) "
        "VALUES (:id,:owner,:goal,NULL,:artifact,:snapshot,:hash,:type,:sensitive,:status)"
    )

    def insert_claim_body(connection, values: dict[str, object]) -> None:
        connection.execute(
            text(
                "INSERT INTO claim_bodies(claim_id,owner_id,goal_id,claim_text) "
                "VALUES (:id,:owner,:goal,:text)"
            ),
            values,
        )

    for claim_type, sensitive in (
        ("fact", 1),
        ("disputed", 0),
        ("comparative", 0),
        ("time-or-version-dependent", 0),
    ):
        with (
            pytest.raises(IntegrityError, match="required claim"),
            engine.begin() as connection,
        ):
            connection.execute(
                insert_claim,
                claim_values(
                    f"published-{claim_type}", claim_type, sensitive, "published"
                ),
            )

    routine_id = "routine-uncited"
    with engine.begin() as connection:
        values = claim_values(routine_id, "routine", 0, "published")
        connection.execute(insert_claim, values)
        insert_claim_body(connection, values)
    assert client.get(f"/api/v1/claims/{routine_id}").json()["citations"] == []

    required_id = "pending-sensitive-fact"
    with engine.begin() as connection:
        values = claim_values(required_id, "fact", 1, "pending")
        connection.execute(insert_claim, values)
        insert_claim_body(connection, values)
    with (
        pytest.raises(IntegrityError, match="required claim citation missing"),
        engine.begin() as connection,
    ):
        connection.execute(
            text("UPDATE claims SET status='published' WHERE id=:id"),
            {"id": required_id},
        )

    source_snapshot_id = "snapshot-for-source-a"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO source_snapshots "
                "(id,owner_id,source_id,retrieved_at,content_hash,status) "
                "VALUES (:id,:owner,:source,:at,'snapshot-hash','unavailable')"
            ),
            {
                "id": source_snapshot_id,
                "owner": owner_id,
                "source": source_id,
                "at": timestamp,
            },
        )
        connection.execute(
            text(
                "INSERT INTO source_snapshot_bodies "
                "(snapshot_id,owner_id,source_id,content_ref,version_label,redacted_failure) "
                "VALUES (:id,:owner,:source,'inline:fixture','v1',NULL)"
            ),
            {
                "id": source_snapshot_id,
                "owner": owner_id,
                "source": source_id,
            },
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO citations "
                "(id,owner_id,goal_id,claim_id,source_id,source_snapshot_id,body_hash,support_kind) "
                "VALUES ('mismatched-snapshot',:owner,:goal,:claim,:other,:snapshot,'mismatch-hash','supports')"
            ),
            {
                "owner": owner_id,
                "goal": goal_id,
                "claim": required_id,
                "other": other_source_id,
                "snapshot": source_snapshot_id,
            },
        )

    citation_id = "valid-sensitive-citation"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO citations "
                "(id,owner_id,goal_id,claim_id,source_id,source_snapshot_id,body_hash,support_kind) "
                "VALUES (:id,:owner,:goal,:claim,:source,:snapshot,:body_hash,'supports')"
            ),
            {
                "id": citation_id,
                "owner": owner_id,
                "goal": goal_id,
                "claim": required_id,
                "source": source_id,
                "snapshot": source_snapshot_id,
                "body_hash": hash_payload({"locator": "section-1", "note": None}),
            },
        )
        connection.execute(
            text(
                "INSERT INTO citation_bodies "
                "(citation_id,owner_id,goal_id,locator,note) "
                "VALUES (:id,:owner,:goal,'section-1',NULL)"
            ),
            {"id": citation_id, "owner": owner_id, "goal": goal_id},
        )
        connection.execute(
            text("UPDATE claims SET status='published' WHERE id=:id"),
            {"id": required_id},
        )
    published = client.get(f"/api/v1/claims/{required_id}")
    assert published.status_code == 200
    assert (
        published.json()["citations"][0]["source"]["availability_status"]
        == "unavailable"
    )

    for statement, message in (
        (
            "UPDATE claims SET claim_hash='rewritten' WHERE id=:id",
            "published claims are immutable",
        ),
        ("DELETE FROM claims WHERE id=:id", "published claims are immutable"),
        (
            "UPDATE citation_bodies SET locator='rewritten' WHERE citation_id=:id",
            "citation_bodies body is immutable",
        ),
        ("DELETE FROM citations WHERE id=:id", "citations header is immutable"),
        (
            "UPDATE source_snapshot_bodies SET version_label='v2' WHERE snapshot_id=:id",
            "source_snapshot_bodies body is immutable",
        ),
        (
            "DELETE FROM source_snapshots WHERE id=:id",
            "source_snapshots header is immutable",
        ),
    ):
        target_id = (
            required_id
            if "claims" in statement
            else citation_id
            if "citation" in statement
            else source_snapshot_id
        )
        with (
            pytest.raises(IntegrityError, match=message),
            engine.begin() as connection,
        ):
            connection.execute(text(statement), {"id": target_id})

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            insert_claim,
            {
                **claim_values("missing-parent", "routine", 0, "pending"),
                "artifact": None,
                "snapshot": None,
            },
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO claims "
                "(id,owner_id,goal_id,content_revision_id,generated_artifact_id,snapshot_id,"
                "claim_hash,claim_type,sensitive,status) "
                "VALUES ('both-parents',:owner,:goal,'content-revision-citation-guards',"
                ":artifact,:snapshot,'invalid-dual-parent-hash','routine',0,'pending')"
            ),
            {
                "owner": owner_id,
                "goal": goal_id,
                "artifact": layer["artifact_id"],
                "snapshot": snapshot_id,
            },
        )

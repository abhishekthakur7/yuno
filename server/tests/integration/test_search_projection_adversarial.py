from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.integration.test_profiles_goals import _owner_id, _seed_approved_graph
from tests.job_assertions import wait_for_job
from yuno.modules.profiles_goals.domain import GoalPath, TargetCapability, TargetLevel
from yuno.modules.profiles_goals.service import create_goal
from yuno.shared.application.unit_of_work import UnitOfWorkFactory


@pytest.fixture
def search_scope(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> Iterator[tuple[str, str, str]]:
    owner_id = _owner_id(uow_factory)
    graph_id = _seed_approved_graph(uow_factory, owner_id)
    with uow_factory() as uow:
        goals = tuple(
            create_goal(
                uow,
                owner_id,
                name=name,
                path=GoalPath.LEARN,
                subject="Java",
                role=None,
                target_level=TargetLevel.SENIOR,
                target_capability=TargetCapability.IMPLEMENT,
                graph_version_id=graph_id,
                approved_graph_exists=True,
            )
            for name in ("Primary search goal", "Other search goal")
        )
        uow.commit()
    yield owner_id, goals[0].id, goals[1].id


def _watermark(uow_factory: UnitOfWorkFactory, owner_id: str) -> str:
    with uow_factory() as uow:
        return uow.search.source_watermark(owner_id)


def _insert_document(
    engine: Engine,
    *,
    document_id: str,
    owner_id: str,
    goal_id: str,
    generation: str,
    entity_id: str,
    title: str,
    entity_type: str = "notebook-entry",
    updated_at: str = "2026-08-13T00:00:00Z",
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO search_documents
                  (id, owner_id, goal_id, generation, entity_type, entity_id,
                   topic_stable_id, version, title, body, tags,
                   projection_version, updated_at)
                VALUES
                  (:id, :owner_id, :goal_id, :generation, :entity_type,
                   :entity_id, NULL, NULL, :title, :body, :tags,
                   'search-v1', :updated_at)
            """),
            {
                "id": document_id,
                "owner_id": owner_id,
                "goal_id": goal_id,
                "generation": generation,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "title": title,
                "body": f"{title} shared-match",
                "tags": "shared-match",
                "updated_at": updated_at,
            },
        )


def _set_index_state(
    engine: Engine,
    *,
    owner_id: str,
    status: str,
    source_watermark: str,
    active_generation: str | None,
    job_id: str | None = None,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO search_index_state
                  (id, owner_id, projection_name, active_generation,
                   projection_version, status, source_watermark,
                   rebuild_job_id, failure_reference, created_at, updated_at)
                VALUES
                  (:id, :owner_id, 'default', :generation, 'search-v1',
                   :status, :watermark, :job_id, NULL,
                   '2026-08-13T00:00:00Z', '2026-08-13T00:00:00Z')
                ON CONFLICT(owner_id, projection_name) DO UPDATE SET
                  active_generation=excluded.active_generation,
                  status=excluded.status,
                  source_watermark=excluded.source_watermark,
                  rebuild_job_id=excluded.rebuild_job_id,
                  failure_reference=NULL,
                  updated_at=excluded.updated_at
            """),
            {
                "id": f"state-{owner_id}",
                "owner_id": owner_id,
                "generation": active_generation,
                "status": status,
                "watermark": source_watermark,
                "job_id": job_id,
            },
        )


def _rebuild_fts(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO search_fts(search_fts) VALUES('rebuild')"))


def test_ready_fts_joins_acl_source_and_uses_only_active_generation(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    search_scope: tuple[str, str, str],
) -> None:
    owner_id, goal_id, other_goal_id = search_scope
    watermark = _watermark(uow_factory, owner_id)
    _insert_document(
        engine,
        document_id="active-owned",
        owner_id=owner_id,
        goal_id=goal_id,
        generation="active-generation",
        entity_id="active-owned",
        title="Active owned result",
    )
    _insert_document(
        engine,
        document_id="inactive-owned",
        owner_id=owner_id,
        goal_id=goal_id,
        generation="inactive-generation",
        entity_id="inactive-owned",
        title="Inactive generation result",
    )
    _insert_document(
        engine,
        document_id="other-goal",
        owner_id=owner_id,
        goal_id=other_goal_id,
        generation="active-generation",
        entity_id="other-goal",
        title="Other goal result",
    )
    _set_index_state(
        engine,
        owner_id=owner_id,
        status="ready",
        source_watermark=watermark,
        active_generation="active-generation",
    )
    _rebuild_fts(engine)

    response = client.get(
        "/api/v1/search",
        params={"q": "shared-match", "goal_id": goal_id},
    )

    assert response.status_code == 200, response.text
    assert response.json()["degraded"] is False
    assert [item["entity_id"] for item in response.json()["results"]] == [
        "active-owned"
    ]


@pytest.mark.parametrize("status", ["stale", "unavailable"])
def test_non_ready_states_use_deterministic_degraded_owned_goal_fallback(
    status: str,
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    search_scope: tuple[str, str, str],
) -> None:
    owner_id, goal_id, other_goal_id = search_scope
    for document_id, title in (
        ("z-result", "Zulu result"),
        ("a-result", "alpha result"),
    ):
        _insert_document(
            engine,
            document_id=document_id,
            owner_id=owner_id,
            goal_id=goal_id,
            generation="latest-generation",
            entity_id=document_id,
            title=title,
            updated_at="2026-08-13T01:00:00Z",
        )
    _insert_document(
        engine,
        document_id="old-generation",
        owner_id=owner_id,
        goal_id=goal_id,
        generation="old-generation",
        entity_id="old-generation",
        title="Old result",
    )
    _insert_document(
        engine,
        document_id=f"other-goal-{status}",
        owner_id=owner_id,
        goal_id=other_goal_id,
        generation="latest-generation",
        entity_id="other-goal",
        title="Other goal result",
        updated_at="2026-08-13T01:00:00Z",
    )
    _set_index_state(
        engine,
        owner_id=owner_id,
        status=status,
        source_watermark=_watermark(uow_factory, owner_id),
        active_generation="old-generation",
    )

    first = client.get(
        "/api/v1/search",
        params={"q": "shared-match", "goal_id": goal_id},
    )
    second = client.get(
        "/api/v1/search",
        params={"q": "shared-match", "goal_id": goal_id},
    )

    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    assert first.json()["index_status"] == status
    assert first.json()["degraded"] is True
    assert [item["entity_id"] for item in first.json()["results"]] == [
        "a-result",
        "z-result",
    ]
    assert all(item["degraded"] is True for item in first.json()["results"])


@pytest.mark.parametrize("status", ["rebuilding", "failed"])
def test_rebuild_or_failure_keeps_serving_the_prior_active_fts_generation(
    status: str,
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    search_scope: tuple[str, str, str],
) -> None:
    owner_id, goal_id, other_goal_id = search_scope
    _insert_document(
        engine,
        document_id=f"prior-{status}",
        owner_id=owner_id,
        goal_id=goal_id,
        generation="prior-active",
        entity_id="prior-result",
        title="Prior active result",
    )
    _insert_document(
        engine,
        document_id=f"partial-{status}",
        owner_id=owner_id,
        goal_id=goal_id,
        generation="partial-candidate",
        entity_id="partial-result",
        title="Partial candidate result",
        updated_at="2026-08-13T01:00:00Z",
    )
    _insert_document(
        engine,
        document_id=f"other-{status}",
        owner_id=owner_id,
        goal_id=other_goal_id,
        generation="prior-active",
        entity_id="other-result",
        title="Other goal result",
    )
    _set_index_state(
        engine,
        owner_id=owner_id,
        status=status,
        source_watermark=_watermark(uow_factory, owner_id),
        active_generation="prior-active",
    )
    _rebuild_fts(engine)

    response = client.get(
        "/api/v1/search",
        params={"q": "shared match", "goal_id": goal_id},
    )

    assert response.status_code == 200, response.text
    assert response.json()["index_status"] == status
    assert response.json()["degraded"] is False
    assert [item["entity_id"] for item in response.json()["results"]] == [
        "prior-result"
    ]
    assert response.json()["results"][0]["degraded"] is False


def test_rebuild_is_idempotent_and_indexes_only_eligible_projection_sources(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    search_scope: tuple[str, str, str],
) -> None:
    owner_id, goal_id, _ = search_scope
    with uow_factory() as uow:
        generation = uow.search.rebuild(owner_id, "direct-rebuild")
        uow.commit()
    with uow_factory() as uow:
        replay_generation = uow.search.rebuild(owner_id, "direct-rebuild")
        uow.commit()

    with engine.connect() as connection:
        projected = connection.execute(
            text("""
                SELECT goal_id, entity_type, entity_id, COUNT(*) count
                FROM search_documents
                WHERE owner_id=:owner_id AND generation=:generation
                GROUP BY goal_id, entity_type, entity_id
                ORDER BY goal_id, entity_type, entity_id
            """),
            {"owner_id": owner_id, "generation": generation},
        ).all()
    assert replay_generation == generation
    assert projected
    assert all(row.count == 1 for row in projected)
    assert {row.entity_type for row in projected} == {"canonical-topic"}
    assert len(projected) == 2

    result = client.get("/api/v1/search", params={"q": "Queues", "goal_id": goal_id})
    assert result.status_code == 200, result.text
    assert result.json()["degraded"] is False
    assert [item["entity_type"] for item in result.json()["results"]] == [
        "canonical-topic"
    ]


def test_failed_partial_rebuild_preserves_previous_generation_and_results(
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    search_scope: tuple[str, str, str],
) -> None:
    owner_id, goal_id, _ = search_scope
    watermark = _watermark(uow_factory, owner_id)
    _insert_document(
        engine,
        document_id="preserved",
        owner_id=owner_id,
        goal_id=goal_id,
        generation="preserved-generation",
        entity_id="preserved",
        title="Preserved result",
    )
    _set_index_state(
        engine,
        owner_id=owner_id,
        status="ready",
        source_watermark=watermark,
        active_generation="preserved-generation",
    )
    _rebuild_fts(engine)

    with (
        pytest.raises(RuntimeError, match="injected partial rebuild"),
        uow_factory() as uow,
    ):
        uow.search.mark_rebuilding(owner_id, "failed-job")
        uow.search._session.execute(  # noqa: SLF001 - fault injection
            text("""
                INSERT INTO search_documents
                  (id, owner_id, goal_id, generation, entity_type, entity_id,
                   title, body, tags, projection_version, updated_at)
                VALUES
                  ('partial', :owner_id, :goal_id, 'candidate-generation',
                   'notebook-entry', 'partial', 'Partial result',
                   'shared-match', 'shared-match', 'search-v1',
                   '2026-08-13T02:00:00Z')
            """),
            {"owner_id": owner_id, "goal_id": goal_id},
        )
        raise RuntimeError("injected partial rebuild")

    with uow_factory() as uow:
        state = uow.search.state(owner_id)
        uow.search.mark_failed(owner_id, "failed-job", "safe-rebuild-failure")
        uow.commit()
    assert state.active_generation == "preserved-generation"

    response = client.get(
        "/api/v1/search",
        params={"q": "shared-match", "goal_id": goal_id},
    )
    status = client.get("/api/v1/search-index/status")
    assert response.status_code == 200
    assert [item["entity_id"] for item in response.json()["results"]] == ["preserved"]
    assert status.status_code == 200
    assert status.json()["status"] == "failed"
    assert status.json()["active_generation"] == "preserved-generation"
    assert status.json()["failure_reference"] == "safe-rebuild-failure"
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM search_documents WHERE id='partial'")
            )
            == 0
        )


def test_search_route_contracts_and_rebuild_replay_keep_authoritative_job_reference(
    client: TestClient,
    search_scope: tuple[str, str, str],
) -> None:
    _, goal_id, _ = search_scope
    assert client.get("/api/v1/search", params={"goal_id": goal_id}).status_code == 422
    assert client.post("/api/v1/search-index/rebuild").status_code == 400

    first = client.post(
        "/api/v1/search-index/rebuild",
        headers={"Idempotency-Key": "adversarial-search-rebuild"},
    )
    assert first.status_code == 202, first.text
    assert first.json()["kind"] == "rebuild_index"
    assert first.json()["lane"] == "background"
    assert first.json()["schema_version"] == "search-v1"
    wait_for_job(client, first)

    replay = client.post(
        "/api/v1/search-index/rebuild",
        headers={"Idempotency-Key": "adversarial-search-rebuild"},
    )
    assert replay.status_code == 202, replay.text
    assert replay.json()["job_id"] == first.json()["job_id"]
    assert replay.json()["deduplicated"] is True
    status = client.get("/api/v1/search-index/status")
    assert status.status_code == 200
    assert status.json()["status"] == "ready"
    assert status.json()["rebuild_job_id"] == first.json()["job_id"]


@pytest.mark.parametrize(
    "query",
    [
        '"',
        "shared-match OR",
        "NEAR(",
        "title:shared-match",
    ],
)
def test_search_treats_user_input_as_literal_text_instead_of_raw_fts_syntax(
    query: str,
    client: TestClient,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    search_scope: tuple[str, str, str],
) -> None:
    owner_id, goal_id, _ = search_scope
    _insert_document(
        engine,
        document_id=f"literal-{abs(hash(query))}",
        owner_id=owner_id,
        goal_id=goal_id,
        generation="literal-generation",
        entity_id=f"literal-{abs(hash(query))}",
        title="Literal shared match title",
    )
    _set_index_state(
        engine,
        owner_id=owner_id,
        status="ready",
        source_watermark=_watermark(uow_factory, owner_id),
        active_generation="literal-generation",
    )
    _rebuild_fts(engine)

    response = client.get("/api/v1/search", params={"q": query, "goal_id": goal_id})

    assert response.status_code == 200, response.text


def test_search_rejects_whitespace_only_query_as_a_validation_error(
    client: TestClient, search_scope: tuple[str, str, str]
) -> None:
    _, goal_id, _ = search_scope
    response = client.get("/api/v1/search", params={"q": "   ", "goal_id": goal_id})
    assert response.status_code == 422, response.text

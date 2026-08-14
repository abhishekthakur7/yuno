"""Integration tests for `GET /api/v1/canonical/versions` and
`GET /api/v1/canonical/versions/{id}` (spec §5.2).

Every topic id/title/subject below is transparently synthetic
(`fixture-topic-*`). Canonical graph rows are seeded directly through
`uow.canonical` (the real repository) so what's under test is the
production read path exactly as the offline publisher would leave it --
version + dependent material + `EditorialApproval` inserted, then
committed.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    RelationType,
    Topic,
    TopicIdentity,
    TopicRelation,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id

_ERROR_ENVELOPE_KEYS = {"code", "message", "request_id", "correlation_id", "retryable"}


@pytest.fixture
def owner_id(client: TestClient, uow_factory: UnitOfWorkFactory) -> str:
    """The singleton local owner the app's lifespan already provisioned
    (`ensure_local_owner`) when `client` started -- read back so
    `canonical_graph_versions.creator_owner_id`'s FK is satisfied by the
    same row production code would use.
    """
    del client  # triggers the app's lifespan before this reads it back
    with uow_factory() as uow:
        owner = uow.owners.get_local_owner()
    assert owner is not None
    return owner.id


def _seed_topic_identity(uow_factory: UnitOfWorkFactory, *, stable_id: str) -> None:
    with uow_factory() as uow:
        uow.canonical.create_topic_identity(
            TopicIdentity(
                stable_id=stable_id,
                stable_slug=f"{stable_id}-slug",
                created_at=now_text(SystemClock()),
                retired_at=None,
            )
        )
        uow.commit()


def _seed_version(
    uow_factory: UnitOfWorkFactory,
    *,
    owner_id: str,
    approve: bool,
    topics: Sequence[tuple[str, str]] = (),
    relations: Sequence[tuple[str, str, RelationType]] = (),
) -> str:
    """Seed one `canonical_graph_versions` row plus its `topics`/
    `topic_relations`, and -- when `approve` is True -- an `EditorialApproval`
    row last, mirroring spec §6.1 step 4's insert order. `approve=False`
    produces a half-seeded version, unreadable through every read path
    exercised below.
    """
    version_id = new_id()
    created_at = now_text(SystemClock())
    with uow_factory() as uow:
        uow.canonical.create_version(
            CanonicalGraphVersion(
                id=version_id,
                version_label=f"fixture-version-{version_id}",
                manifest_version="fixture-manifest-v1",
                manifest_hash=f"fixture-hash-{version_id}",
                status=CanonicalVersionStatus.PUBLISHED
                if approve
                else CanonicalVersionStatus.PENDING_APPROVAL,
                creator_owner_id=owner_id,
                created_at=created_at,
                published_at=created_at if approve else None,
                supersedes_version_id=None,
            )
        )
        for stable_id, title in topics:
            uow.canonical.add_topic(
                Topic(
                    graph_version_id=version_id,
                    stable_id=stable_id,
                    title=title,
                    subject="dsa",
                    scope_tags=("fixture-tag",),
                    level_tag="fixture-level",
                    target_capability="fixture-capability",
                    recommended_layer="fixture-layer",
                    checkpoint_start=0,
                    checkpoint_end=1,
                )
            )
        for from_id, to_id, relation_type in relations:
            uow.canonical.add_relation(
                TopicRelation(
                    id=new_id(),
                    graph_version_id=version_id,
                    from_stable_id=from_id,
                    to_stable_id=to_id,
                    relation_type=relation_type,
                    rationale="fixture-rationale",
                )
            )
        if approve:
            uow.canonical.record_approval(
                EditorialApproval(
                    id=new_id(),
                    graph_version_id=version_id,
                    approver_owner_id=owner_id,
                    approver_role="designated_editorial_approver",
                    basis_ref='"fixture-basis-ref"',
                    approved_at=created_at,
                )
            )
        uow.commit()
    return version_id


def test_list_returns_only_approved_versions(
    client: TestClient, uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    approved_id = _seed_version(uow_factory, owner_id=owner_id, approve=True)
    half_seeded_id = _seed_version(uow_factory, owner_id=owner_id, approve=False)

    response = client.get("/api/v1/canonical/versions")

    assert response.status_code == 200
    ids = {entry["id"] for entry in response.json()}
    assert approved_id in ids
    assert half_seeded_id not in ids


def test_get_approved_version_returns_topics_and_relations(
    client: TestClient, uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    _seed_topic_identity(uow_factory, stable_id="fixture-topic-a")
    _seed_topic_identity(uow_factory, stable_id="fixture-topic-b")
    version_id = _seed_version(
        uow_factory,
        owner_id=owner_id,
        approve=True,
        topics=[("fixture-topic-a", "Fixture Topic A"), ("fixture-topic-b", "Fixture Topic B")],
        relations=[("fixture-topic-a", "fixture-topic-b", RelationType.PREREQUISITE)],
    )

    response = client.get(f"/api/v1/canonical/versions/{version_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == version_id
    assert {topic["stable_id"] for topic in body["topics"]} == {"fixture-topic-a", "fixture-topic-b"}
    assert len(body["relations"]) == 1
    relation = body["relations"][0]
    assert relation["from_stable_id"] == "fixture-topic-a"
    assert relation["to_stable_id"] == "fixture-topic-b"
    assert relation["relation_type"] == "prerequisite"
    # Never leaks who ran the offline publisher.
    assert "creator_owner_id" not in body
    assert "approver_owner_id" not in body


def test_half_seeded_version_404s_on_list_and_detail(
    client: TestClient, uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    """A version with no `EditorialApproval` row is indistinguishable from
    a nonexistent one on both read paths (spec §5.1's "absent/out of
    scope" rule)."""
    _seed_topic_identity(uow_factory, stable_id="fixture-topic-c")
    half_seeded_id = _seed_version(
        uow_factory,
        owner_id=owner_id,
        approve=False,
        topics=[("fixture-topic-c", "Fixture Topic C")],
    )

    list_response = client.get("/api/v1/canonical/versions")
    assert half_seeded_id not in {entry["id"] for entry in list_response.json()}

    detail_response = client.get(f"/api/v1/canonical/versions/{half_seeded_id}")
    assert detail_response.status_code == 404


def test_nonexistent_version_404s_with_matching_error_envelope(client: TestClient) -> None:
    response = client.get(f"/api/v1/canonical/versions/{new_id()}")

    assert response.status_code == 404
    body = response.json()
    assert _ERROR_ENVELOPE_KEYS <= body.keys()
    assert body["code"] == "not_found"
    assert body["retryable"] is False


def test_half_seeded_and_nonexistent_versions_produce_the_same_error_shape(
    client: TestClient, uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    half_seeded_id = _seed_version(uow_factory, owner_id=owner_id, approve=False)

    half_seeded_response = client.get(f"/api/v1/canonical/versions/{half_seeded_id}")
    nonexistent_response = client.get(f"/api/v1/canonical/versions/{new_id()}")

    assert half_seeded_response.status_code == nonexistent_response.status_code == 404
    assert half_seeded_response.json()["code"] == nonexistent_response.json()["code"] == "not_found"

"""Integration tests for `SqlAlchemyCanonicalRepository`: a graph version
without an `EditorialApproval` row is invisible to every read
(`get_published_version`, `list_published_versions`, `get_published_topics`,
`get_published_relations`). Each is checked both ways -- empty/`None` for a
half-seeded version, populated once `record_approval` has run -- so a method
that always returns empty cannot pass silently.

Publish-time existence checks (`version_label_exists`, `manifest_hash_exists`,
`topic_identity_exists`) are unfiltered by design and must see unapproved
material too.
"""

from __future__ import annotations

import pytest

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


@pytest.fixture
def owner_id(uow_factory: UnitOfWorkFactory) -> str:
    with uow_factory() as uow:
        owner = uow.owners.create_local_owner("Owner")
        uow.commit()
    return owner.id


def _seed_topic(uow, *, graph_version_id: str, stable_id: str, title: str) -> None:
    uow.canonical.create_topic_identity(
        TopicIdentity(
            stable_id=stable_id,
            stable_slug=f"slug-{stable_id}",
            created_at=now_text(SystemClock()),
            retired_at=None,
        )
    )
    uow.canonical.add_topic(
        Topic(
            graph_version_id=graph_version_id,
            stable_id=stable_id,
            title=title,
            subject="java",
            scope_tags=("fixture-tag",),
            level_tag="intro",
            target_capability="fixture-capability",
            recommended_layer="fixture-layer",
            checkpoint_start=0,
            checkpoint_end=1,
        )
    )


def _seed_version(
    uow,
    *,
    owner_id: str,
    approved: bool,
) -> tuple[str, str, str, str]:
    """Seed one graph version with two topics and one relation between them;
    approve it iff `approved`. Returns
    `(version_id, topic_a_stable_id, topic_b_stable_id, relation_id)`.
    """
    version_id = new_id()
    uow.canonical.create_version(
        CanonicalGraphVersion(
            id=version_id,
            version_label=f"fixture-label-{version_id}",
            manifest_version="v1",
            manifest_hash=f"fixture-hash-{version_id}",
            status=CanonicalVersionStatus.PUBLISHED,
            creator_owner_id=owner_id,
            created_at=now_text(SystemClock()),
            published_at=now_text(SystemClock()),
            supersedes_version_id=None,
        )
    )
    topic_a = f"fixture-topic-a-{version_id}"
    topic_b = f"fixture-topic-b-{version_id}"
    _seed_topic(uow, graph_version_id=version_id, stable_id=topic_a, title="Fixture Topic A")
    _seed_topic(uow, graph_version_id=version_id, stable_id=topic_b, title="Fixture Topic B")

    relation_id = new_id()
    uow.canonical.add_relation(
        TopicRelation(
            id=relation_id,
            graph_version_id=version_id,
            from_stable_id=topic_a,
            to_stable_id=topic_b,
            relation_type=RelationType.PREREQUISITE,
            rationale="fixture-rationale",
        )
    )

    if approved:
        uow.canonical.record_approval(
            EditorialApproval(
                id=new_id(),
                graph_version_id=version_id,
                approver_owner_id=owner_id,
                approver_role="designated_editorial_approver",
                basis_ref='"fixture-basis"',
                approved_at=now_text(SystemClock()),
            )
        )

    return version_id, topic_a, topic_b, relation_id


# ----------------------------------------------------------------------
# get_published_version

def test_get_published_version_none_for_half_seeded_version(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        version_id, _, _, _ = _seed_version(uow, owner_id=owner_id, approved=False)
        uow.commit()

    with uow_factory() as uow:
        assert uow.canonical.get_published_version(version_id) is None


def test_get_published_version_returns_approved_version(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        version_id, _, _, _ = _seed_version(uow, owner_id=owner_id, approved=True)
        uow.commit()

    with uow_factory() as uow:
        version = uow.canonical.get_published_version(version_id)
    assert version is not None
    assert version.id == version_id
    assert version.status is CanonicalVersionStatus.PUBLISHED


# ----------------------------------------------------------------------
# list_published_versions

def test_list_published_versions_excludes_half_seeded_version(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        unapproved_id, _, _, _ = _seed_version(uow, owner_id=owner_id, approved=False)
        approved_id, _, _, _ = _seed_version(uow, owner_id=owner_id, approved=True)
        uow.commit()

    with uow_factory() as uow:
        listed_ids = {version.id for version in uow.canonical.list_published_versions()}
    assert approved_id in listed_ids
    assert unapproved_id not in listed_ids


# ----------------------------------------------------------------------
# get_published_topics

def test_get_published_topics_empty_for_half_seeded_version(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        version_id, _, _, _ = _seed_version(uow, owner_id=owner_id, approved=False)
        uow.commit()

    with uow_factory() as uow:
        assert uow.canonical.get_published_topics(version_id) == []


def test_get_published_topics_returns_topics_for_approved_version(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        version_id, topic_a, topic_b, _ = _seed_version(uow, owner_id=owner_id, approved=True)
        uow.commit()

    with uow_factory() as uow:
        topics = uow.canonical.get_published_topics(version_id)
    assert {topic.stable_id for topic in topics} == {topic_a, topic_b}


# ----------------------------------------------------------------------
# get_published_relations

def test_get_published_relations_empty_for_half_seeded_version(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        version_id, _, _, _ = _seed_version(uow, owner_id=owner_id, approved=False)
        uow.commit()

    with uow_factory() as uow:
        assert uow.canonical.get_published_relations(version_id) == []


def test_get_published_relations_returns_relations_for_approved_version(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        version_id, _, _, relation_id = _seed_version(uow, owner_id=owner_id, approved=True)
        uow.commit()

    with uow_factory() as uow:
        relations = uow.canonical.get_published_relations(version_id)
    assert {relation.id for relation in relations} == {relation_id}


# ----------------------------------------------------------------------
# The approval gate is per-version: an approved version's material never
# leaks into another version's reads.

def test_approved_version_a_topics_do_not_leak_into_version_b_reads(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        version_a, topic_a1, topic_a2, _ = _seed_version(uow, owner_id=owner_id, approved=True)
        version_b, topic_b1, topic_b2, _ = _seed_version(uow, owner_id=owner_id, approved=True)
        uow.commit()

    with uow_factory() as uow:
        topics_a = {topic.stable_id for topic in uow.canonical.get_published_topics(version_a)}
        topics_b = {topic.stable_id for topic in uow.canonical.get_published_topics(version_b)}
    assert topics_a == {topic_a1, topic_a2}
    assert topics_b == {topic_b1, topic_b2}
    assert topics_a.isdisjoint(topics_b)


# ----------------------------------------------------------------------
# Publish-time lookups (see repository.py) are unfiltered by approval
# status: the publisher pre-checks these before writing a new version.

def test_version_label_exists_sees_unapproved_version(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        version_id, _, _, _ = _seed_version(uow, owner_id=owner_id, approved=False)
        uow.commit()

    with uow_factory() as uow:
        assert uow.canonical.version_label_exists(f"fixture-label-{version_id}") is True
        assert uow.canonical.version_label_exists("does-not-exist") is False


def test_manifest_hash_exists_sees_unapproved_version(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        version_id, _, _, _ = _seed_version(uow, owner_id=owner_id, approved=False)
        uow.commit()

    with uow_factory() as uow:
        assert uow.canonical.manifest_hash_exists(f"fixture-hash-{version_id}") is True
        assert uow.canonical.manifest_hash_exists("does-not-exist") is False


def test_topic_identity_exists_sees_unapproved_version_topics(
    uow_factory: UnitOfWorkFactory, owner_id: str
) -> None:
    with uow_factory() as uow:
        _, topic_a, _, _ = _seed_version(uow, owner_id=owner_id, approved=False)
        uow.commit()

    with uow_factory() as uow:
        assert uow.canonical.topic_identity_exists(topic_a) is True
        assert uow.canonical.topic_identity_exists("does-not-exist") is False

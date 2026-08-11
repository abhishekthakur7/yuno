"""`GET /api/v1/canonical/versions` and `GET /api/v1/canonical/versions/{id}`
(spec §5.2 "Canonical reads/diffs", IDK-102).

No write endpoint exists here or anywhere in this API -- D1 forbids
in-app authoring/publication (spec §5.1); only the offline publisher
inserts a `CanonicalGraphVersion`. Reads go through `uow.canonical`'s
approval-gated methods, so an unapproved or half-seeded version is
indistinguishable from a nonexistent one: both render as a plain `404`
(spec §5.1's "absent/out of scope" rule).

`creator_owner_id`/`approver_owner_id` never reach the response: this API
has no authentication (`api/dependencies.get_owner_id`'s docstring), so
naming which owner published or approved a version would leak detail no
caller has a use for.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from yuno.api.contracts import (
    CanonicalTopicRelationResponse,
    CanonicalTopicResponse,
    CanonicalVersionDetailResponse,
    CanonicalVersionSummaryResponse,
)
from yuno.api.dependencies import get_unit_of_work
from yuno.modules.canonical.domain import CanonicalGraphVersion, Topic, TopicRelation
from yuno.modules.canonical.ports import CanonicalUnitOfWork
from yuno.shared.domain.errors import NotFoundError

router = APIRouter(tags=["canonical"])


@router.get("/canonical/versions", response_model=list[CanonicalVersionSummaryResponse])
def list_canonical_versions(
    uow: Annotated[CanonicalUnitOfWork, Depends(get_unit_of_work)],
) -> list[CanonicalVersionSummaryResponse]:
    """List every approved canonical graph version."""
    versions = uow.canonical.list_published_versions()
    return [_version_summary(version) for version in versions]


@router.get("/canonical/versions/{version_id}", response_model=CanonicalVersionDetailResponse)
def get_canonical_version(
    version_id: str,
    uow: Annotated[CanonicalUnitOfWork, Depends(get_unit_of_work)],
) -> CanonicalVersionDetailResponse:
    """Fetch one approved canonical graph version with its published topics
    and relations. Raises `404` whether the version doesn't exist or just
    isn't approved (module docstring).
    """
    version = uow.canonical.get_published_version(version_id)
    if version is None:
        raise NotFoundError(f"Canonical graph version '{version_id}' was not found.")
    topics = uow.canonical.get_published_topics(version_id)
    relations = uow.canonical.get_published_relations(version_id)
    return CanonicalVersionDetailResponse(
        **_version_summary(version).model_dump(),
        topics=[_topic_response(topic) for topic in topics],
        relations=[_relation_response(relation) for relation in relations],
    )


def _version_summary(version: CanonicalGraphVersion) -> CanonicalVersionSummaryResponse:
    return CanonicalVersionSummaryResponse(
        id=version.id,
        version_label=version.version_label,
        manifest_version=version.manifest_version,
        created_at=version.created_at,
        published_at=version.published_at,
        supersedes_version_id=version.supersedes_version_id,
    )


def _topic_response(topic: Topic) -> CanonicalTopicResponse:
    return CanonicalTopicResponse(
        stable_id=topic.stable_id,
        title=topic.title,
        subject=topic.subject,
        scope_tags=list(topic.scope_tags),
        level_tag=topic.level_tag,
        target_capability=topic.target_capability,
        recommended_layer=topic.recommended_layer,
        checkpoint_start=topic.checkpoint_start,
        checkpoint_end=topic.checkpoint_end,
    )


def _relation_response(relation: TopicRelation) -> CanonicalTopicRelationResponse:
    return CanonicalTopicRelationResponse(
        id=relation.id,
        from_stable_id=relation.from_stable_id,
        to_stable_id=relation.to_stable_id,
        relation_type=relation.relation_type.value,
        rationale=relation.rationale,
    )

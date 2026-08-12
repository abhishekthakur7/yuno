"""Canonical curriculum graph domain concepts (spec §4.3's six tables,
spec §9.1's `Canonical draft`/`Canonical published` state rows).

Framework-free (spec §3.2) -- see `yuno.shared.domain`'s docstring for the
rule this module is bound by.

Terminology note: spec §9.1 calls the terminal, immutable state
`published`; spec §4.3 calls the same event "approved" ("approved
versions immutable"). A `CanonicalGraphVersion` becomes `published`
exactly when its `EditorialApproval` row is inserted (spec §6.1 steps
4-5, atomically, last). This module uses `published` as the enum value.

`CanonicalVersionStatus.SUPERSEDED` is derived, never persisted (the
stored `status` CHECK constraint in `models.py` omits it): spec §9.1's
only persisted supersession effect is the *new* version's
`supersedes_version_id` pointing back at the old one -- the old,
already-published (hence immutable) row is never touched. A caller
reports a version as `superseded` by checking whether any other
version's `supersedes_version_id` references it, not by reading a
stored status value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CanonicalVersionStatus(StrEnum):
    """spec §9.1's `Canonical draft`/`Canonical published` state row.

    `AUTHORED`/`CURATED`/`AI_DRAFT`/`VALIDATION_FAILED` describe the
    offline publisher's pre-publish working state (spec §6.1 steps 1-3).
    There is no in-app authoring (D1), so in practice only a manifest
    that reaches `PENDING_APPROVAL` and then `PUBLISHED` in one atomic
    transaction is ever persisted; the earlier states exist for
    completeness against spec §9.1 and for a future offline-tool caller.
    """

    AUTHORED = "authored"
    CURATED = "curated"
    AI_DRAFT = "ai_draft"
    VALIDATION_FAILED = "validation_failed"
    PENDING_APPROVAL = "pending_approval"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    """Derived only -- see module docstring. Never stored or returned by
    a repository read of the `status` column."""


PERSISTED_VERSION_STATUSES: frozenset[CanonicalVersionStatus] = frozenset(
    {
        CanonicalVersionStatus.AUTHORED,
        CanonicalVersionStatus.CURATED,
        CanonicalVersionStatus.AI_DRAFT,
        CanonicalVersionStatus.VALIDATION_FAILED,
        CanonicalVersionStatus.PENDING_APPROVAL,
        CanonicalVersionStatus.PUBLISHED,
    }
)
"""Every value the `status` column's CHECK constraint (`models.py`)
accepts -- everything except the derived `SUPERSEDED`."""


class RelationType(StrEnum):
    """`topic_relations.relation_type` (spec §4.3).

    `PREREQUISITE` is the ordering relation the roadmap topologically
    sorts on (spec §6.2) and must always form a DAG. `SCENARIO` is CUR-02's
    DSA-topic-to-scenario binding. `RELATED` is the one type spec §4.3
    allows to cycle -- see `validation.RELATION_TYPES_ALLOWED_TO_CYCLE`,
    which owns that decision; this enum only names the type.
    """

    PREREQUISITE = "prerequisite"
    SCENARIO = "scenario"
    RELATED = "related"


@dataclass(frozen=True)
class CanonicalGraphVersion:
    """`canonical_graph_versions` row (spec §4.3)."""

    id: str
    version_label: str
    manifest_version: str
    manifest_hash: str
    status: CanonicalVersionStatus
    creator_owner_id: str
    created_at: str
    published_at: str | None
    supersedes_version_id: str | None


@dataclass(frozen=True)
class TopicIdentity:
    """`topic_identities` row: a stable identity persisting across graph
    versions (spec §4.3)."""

    stable_id: str
    stable_slug: str
    created_at: str
    retired_at: str | None


@dataclass(frozen=True)
class Topic:
    """`topics` row: one topic within one graph version (spec §4.3).

    `scope_tags` is a tuple of free-form curriculum tags (persisted as a
    JSON array -- see `models.py`). `subject` is the field
    `validation.py`'s CUR-01/CUR-02 boundary check binds on.
    """

    graph_version_id: str
    stable_id: str
    title: str
    subject: str
    scope_tags: tuple[str, ...]
    level_tag: str
    target_capability: str
    recommended_layer: str
    checkpoint_start: int
    checkpoint_end: int


@dataclass(frozen=True)
class TopicRelation:
    """`topic_relations` row (spec §4.3)."""

    id: str
    graph_version_id: str
    from_stable_id: str
    to_stable_id: str
    relation_type: RelationType
    rationale: str | None


@dataclass(frozen=True)
class ContentRevision:
    """`content_revisions` row (spec §4.3). Immutable once inserted."""

    id: str
    graph_version_id: str
    topic_stable_id: str
    layer: str
    kind: str
    status: str
    markdown_ref: str
    markdown_hash: str
    prompt_template_version: str | None
    creator_owner_id: str
    supersedes_revision_id: str | None
    created_at: str


@dataclass(frozen=True)
class EditorialApproval:
    """`editorial_approvals` row (spec §4.3). Inserted last in the D1
    publish transaction; immutable; `graph_version_id` is UNIQUE."""

    id: str
    graph_version_id: str
    approver_owner_id: str
    approver_role: str
    basis_ref: str
    approved_at: str


@dataclass(frozen=True)
class CanonicalGraphManifest:
    """The offline publisher's not-yet-persisted publish unit: everything
    spec §6.1 step 4 inserts as one version's dependent material, before
    any of it becomes a `CanonicalGraphVersion`/`Topic`/... row.

    Framework-free and DB-agnostic on purpose: `validation.py`'s graph
    validation (spec §6.1 step 2) runs against this in-memory shape so a
    bad manifest is rejected before the publisher opens a write
    transaction (spec §3.4: no long-running work inside one).
    """

    version_label: str
    manifest_version: str
    manifest_hash: str
    topics: tuple[Topic, ...]
    relations: tuple[TopicRelation, ...] = ()
    content_revisions: tuple[ContentRevision, ...] = ()


class MergeProposalStatus(StrEnum):
    AWAITING = "awaiting"
    POSTPONED = "postponed"
    DISMISSED = "dismissed"
    ACCEPTED = "accepted"


class MergeEntityType(StrEnum):
    TOPIC = "topic"
    RELATION = "relation"
    CONTENT = "content"


class MergeChangeType(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


class MergeResolution(StrEnum):
    ACCEPT_CANONICAL = "accept-canonical"
    OVERLAY_WINS = "overlay-wins"
    RETAIN_LOCAL = "retain-local"


@dataclass(frozen=True)
class CanonicalMergeProposal:
    id: str
    owner_id: str
    goal_id: str
    base_version_id: str
    target_version_id: str
    goal_row_version: int
    diff_hash: str
    local_state_hash: str
    status: MergeProposalStatus
    created_at: str
    decided_at: str | None = None


@dataclass(frozen=True)
class MergeItem:
    id: str
    proposal_id: str
    entity_type: MergeEntityType
    change_type: MergeChangeType
    topic_id: str | None
    title: str
    summary: str
    impact: str
    conflict_type: str | None
    selected: bool
    recommended_resolution: MergeResolution
    chosen_resolution: MergeResolution | None
    resolution_explanation: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CanonicalMergeFollowup:
    id: str
    owner_id: str
    goal_id: str
    proposal_id: str
    kind: str
    payload: dict[str, Any]
    status: str
    job_id: str | None
    created_at: str

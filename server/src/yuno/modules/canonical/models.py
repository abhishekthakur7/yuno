"""Canonical curriculum graph ORM models: the six tables of spec §4.3
(`canonical_graph_versions`, `topic_identities`, `topics`,
`topic_relations`, `content_revisions`, `editorial_approvals`).

Ownership decision: none of these six tables carries `owner_id`, and all
six are listed in `OWNERLESS_TABLES` (`yuno.shared.infrastructure.base`).
A canonical graph version is authored, validated and approved once by
the offline D1 publisher and then read by every owner's roadmap/topic/
search/generation/diff reads alike (spec §6.1, §6.2) -- it is shared
reference content, not data any single owner's UoW creates or owns.
`creator_owner_id`/`approver_owner_id` still record *which* owner acted,
same as `audit_events.owner_id` records an actor without making
`audit_events` owner-scoped -- but unlike `audit_events` (genuinely one
row per owner action), a `CanonicalGraphVersion`/`Topic`/... row belongs
to every owner's reads, not to whichever owner ran the publisher.
Tagging these tables `owner_id` would incorrectly scope shared curriculum
to a single local owner.

`status` CHECK constraints and the append/immutability triggers are owned
by the accompanying Alembic migration, not this file -- see that
migration's docstring and `442e2f56adb9`'s warning about
`batch_alter_table` silently dropping raw-SQL triggers. They enforce spec
§4.3's "SQLite triggers reject UPDATE/DELETE on any graph, topic,
relation, content or approval row belonging to an approved version" and
`editorial_approvals.graph_version_id`'s UNIQUE invariant at the database
layer, not merely by convention.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import Base, id_column, utc_timestamp_column

# `status`'s stored vocabulary omits `superseded` -- see `domain.py`'s
# `CanonicalVersionStatus`/`PERSISTED_VERSION_STATUSES` docstrings for why
# supersession is a derived, never-persisted read, not a stored value.
_VERSION_STATUS_VALUES = "('authored','curated','ai_draft','validation_failed','pending_approval','published')"

_RELATION_TYPE_VALUES = "('prerequisite','scenario','related')"


class CanonicalGraphVersionRow(Base):
    """`canonical_graph_versions` -- approved versions immutable; visible
    to reads only through the `editorial_approvals` join (spec §4.3)."""

    __tablename__ = "canonical_graph_versions"
    __table_args__ = (
        CheckConstraint(f"status IN {_VERSION_STATUS_VALUES}", name="status_valid"),
    )

    id: Mapped[str] = id_column()
    version_label: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    manifest_version: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    creator_owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()
    published_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    # Self-referential: set on the *new* version at insert time, pointing
    # back at the version it supersedes. Never mutated onto the old row
    # (see `domain.py`'s `CanonicalVersionStatus.SUPERSEDED` docstring).
    supersedes_version_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical_graph_versions.id"), nullable=True
    )


class TopicIdentityRow(Base):
    """`topic_identities` -- stable across graph versions (spec §4.3)."""

    __tablename__ = "topic_identities"

    stable_id: Mapped[str] = id_column()
    stable_slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()
    retired_at: Mapped[str | None] = utc_timestamp_column(nullable=True)


class TopicRow(Base):
    """`topics` -- one topic within one graph version; composite PK of
    graph version + stable ID (spec §4.3).

    No `content_revision_id` column here despite spec §4.3's column list:
    such a pointer would need a composite FK back to `content_revisions`,
    which itself carries a composite FK to this table -- a genuine FK
    cycle that would force splitting the D1 publish transaction's insert
    order into topic-then-content-then-update-topic instead of one clean
    insert-only sequence (spec §6.1 step 4). `content_revisions` already
    carries `(graph_version_id, topic_stable_id)`, so "which content
    revisions exist for this topic" is answered by querying that table,
    not by a redundant pointer here.
    """

    __tablename__ = "topics"
    __table_args__ = (
        ForeignKeyConstraint(
            ["stable_id"], ["topic_identities.stable_id"], name="fk_topics_stable_id_topic_identities"
        ),
        Index("ix_topics_graph_version_subject", "graph_version_id", "subject"),
    )

    graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_graph_versions.id"), primary_key=True
    )
    stable_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON-encoded array of free-form curriculum tags (spec §4.3's
    # "scope/level tags"; `level_tag` below is the one distinguished
    # level tag). Framework-free callers use `Topic.scope_tags` (a
    # tuple); `repository.py` owns the JSON encode/decode at this
    # boundary.
    scope_tags: Mapped[str] = mapped_column(Text, nullable=False)
    level_tag: Mapped[str] = mapped_column(Text, nullable=False)
    target_capability: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_layer: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_start: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_end: Mapped[int] = mapped_column(Integer, nullable=False)


class TopicRelationRow(Base):
    """`topic_relations` -- composite graph FKs to `topics`; prerequisite
    cycles rejected; only explicitly configured non-prerequisite relation
    types may cycle (spec §4.3, enforced by `validation.py`, not by any DB
    constraint -- SQLite has no native DAG/acyclicity constraint)."""

    __tablename__ = "topic_relations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["graph_version_id", "from_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_topic_relations_from_topics",
        ),
        ForeignKeyConstraint(
            ["graph_version_id", "to_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_topic_relations_to_topics",
        ),
        CheckConstraint(f"relation_type IN {_RELATION_TYPE_VALUES}", name="relation_type_valid"),
        UniqueConstraint(
            "graph_version_id", "from_stable_id", "to_stable_id", "relation_type", name="uq_topic_relation_tuple"
        ),
    )

    id: Mapped[str] = id_column()
    graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_graph_versions.id"), nullable=False
    )
    from_stable_id: Mapped[str] = mapped_column(Text, nullable=False)
    to_stable_id: Mapped[str] = mapped_column(Text, nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContentRevisionRow(Base):
    """`content_revisions` -- immutable once inserted; unique per
    graph/topic/layer/hash (spec §4.3).

    `kind` (which layer-content shape a revision is -- explanation,
    example, ...) has no CHECK-enumerated vocabulary: which kinds the
    MVP's layers need is IDK-001/IDK-104/IDK-106 territory, out of scope
    here, so a fixed set would be invented content. `kind_non_blank`
    still satisfies spec §4.1's "every enum-ish column carries a CHECK
    constraint" convention by constraining structure (non-blank) rather
    than a vocabulary this module has no basis to fix.

    `status`, by contrast, has only one reachable value: like
    `canonical_graph_versions.status`, a `content_revisions` row is only
    ever inserted already-finalized inside the D1 publish transaction --
    there is no in-app authoring/draft-editing path (D1) that would leave
    one in an intermediate state. `status_valid` reflects that directly.
    """

    __tablename__ = "content_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["graph_version_id", "topic_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_content_revisions_topics",
        ),
        UniqueConstraint(
            "graph_version_id", "topic_stable_id", "layer", "markdown_hash", name="uq_content_revision_hash"
        ),
        CheckConstraint("length(trim(kind)) > 0", name="kind_non_blank"),
        CheckConstraint("status IN ('published')", name="status_valid"),
    )

    id: Mapped[str] = id_column()
    graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_graph_versions.id"), nullable=False
    )
    topic_stable_id: Mapped[str] = mapped_column(Text, nullable=False)
    layer: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_ref: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_hash: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    creator_owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    supersedes_revision_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("content_revisions.id"), nullable=True
    )
    created_at: Mapped[str] = utc_timestamp_column()


class EditorialApprovalRow(Base):
    """`editorial_approvals` -- inserted last in the D1 publish
    transaction; immutable; `graph_version_id` UNIQUE (spec §4.3, IDK-102
    "Data and invariants")."""

    __tablename__ = "editorial_approvals"
    __table_args__ = (
        # D1 keeps learner/editor roles distinct (spec §4.2) -- an
        # approval is only ever recorded under the editorial role,
        # mirroring `owner_role_grants.role`'s CHECK.
        CheckConstraint("approver_role IN ('designated_editorial_approver')", name="approver_role_valid"),
    )

    id: Mapped[str] = id_column()
    graph_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_graph_versions.id"), unique=True, nullable=False
    )
    approver_owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    approver_role: Mapped[str] = mapped_column(Text, nullable=False)
    basis_ref: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[str] = utc_timestamp_column()

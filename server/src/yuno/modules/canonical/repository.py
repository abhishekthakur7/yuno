"""SQLAlchemy adapter for `CanonicalGraphRepository` (spec §4.3, §6.1).

Every write method is a bare single-table insert, deliberately -- see
`ports.py` for why: sequencing/atomicity is the D1 offline publisher's
job (`yuno.modules.canonical.publisher`), not this repository's. No
method here updates or deletes an existing row; the migration's SQLite
triggers are the backstop, but this adapter also structurally offers no
such method to call.

Read methods are approval-gated by construction: every one of
`get_published_version`/`list_published_versions`/`get_published_topics`/
`get_published_relations` joins against `editorial_approvals`, so a
half-seeded version with no recorded approval is invisible through all
four, not merely filtered by a `status` column a caller could bypass.

Maps ORM rows to/from the frozen `canonical.domain` dataclasses; ORM rows
never cross the repository boundary. `topics.scope_tags` is the one
column needing a real encode/decode step (JSON array text <-> tuple of
str) -- see `models.py` for why that boundary lives here rather than on
the ORM column itself.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select, update

from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalMergeFollowup,
    CanonicalMergeProposal,
    CanonicalVersionStatus,
    ContentRevision,
    EditorialApproval,
    MergeChangeType,
    MergeEntityType,
    MergeItem,
    MergeProposalStatus,
    MergeResolution,
    RelationType,
    Topic,
    TopicIdentity,
    TopicRelation,
)
from yuno.modules.canonical.models import (
    CanonicalGraphVersionRow,
    CanonicalMergeFollowupRow,
    CanonicalMergeProposalRow,
    ContentRevisionRow,
    EditorialApprovalRow,
    MergeItemRow,
    TopicIdentityRow,
    TopicRelationRow,
    TopicRow,
)
from yuno.shared.infrastructure.repository import SqlAlchemyRepository


class SqlAlchemyCanonicalRepository(SqlAlchemyRepository):
    """`CanonicalGraphRepository` adapter, satisfied structurally per
    `ports.py` -- no explicit Protocol inheritance.
    """

    __slots__ = ()

    # --- Writes -------------------------------------------------------

    def create_topic_identity(self, identity: TopicIdentity) -> None:
        self._session.add(
            TopicIdentityRow(
                stable_id=identity.stable_id,
                stable_slug=identity.stable_slug,
                created_at=identity.created_at,
                retired_at=identity.retired_at,
            )
        )
        # Flush (not just add): the session factory disables autoflush,
        # so a later `topic_identity_exists`/`add_topic` call inside the
        # same publish transaction would otherwise not see this row yet.
        self._session.flush()

    def create_version(self, version: CanonicalGraphVersion) -> None:
        self._session.add(
            CanonicalGraphVersionRow(
                id=version.id,
                version_label=version.version_label,
                manifest_version=version.manifest_version,
                manifest_hash=version.manifest_hash,
                status=version.status.value,
                creator_owner_id=version.creator_owner_id,
                created_at=version.created_at,
                published_at=version.published_at,
                supersedes_version_id=version.supersedes_version_id,
            )
        )
        self._session.flush()

    def add_topic(self, topic: Topic) -> None:
        self._session.add(
            TopicRow(
                graph_version_id=topic.graph_version_id,
                stable_id=topic.stable_id,
                title=topic.title,
                subject=topic.subject,
                scope_tags=json.dumps(list(topic.scope_tags)),
                level_tag=topic.level_tag,
                target_capability=topic.target_capability,
                recommended_layer=topic.recommended_layer,
                checkpoint_start=topic.checkpoint_start,
                checkpoint_end=topic.checkpoint_end,
            )
        )
        self._session.flush()

    def add_relation(self, relation: TopicRelation) -> None:
        self._session.add(
            TopicRelationRow(
                id=relation.id,
                graph_version_id=relation.graph_version_id,
                from_stable_id=relation.from_stable_id,
                to_stable_id=relation.to_stable_id,
                relation_type=relation.relation_type.value,
                rationale=relation.rationale,
            )
        )
        self._session.flush()

    def add_content_revision(self, revision: ContentRevision) -> None:
        self._session.add(
            ContentRevisionRow(
                id=revision.id,
                graph_version_id=revision.graph_version_id,
                topic_stable_id=revision.topic_stable_id,
                layer=revision.layer,
                kind=revision.kind,
                status=revision.status,
                markdown_ref=revision.markdown_ref,
                markdown_hash=revision.markdown_hash,
                prompt_template_version=revision.prompt_template_version,
                creator_owner_id=revision.creator_owner_id,
                supersedes_revision_id=revision.supersedes_revision_id,
                created_at=revision.created_at,
            )
        )
        self._session.flush()

    def record_approval(self, approval: EditorialApproval) -> None:
        self._session.add(
            EditorialApprovalRow(
                id=approval.id,
                graph_version_id=approval.graph_version_id,
                approver_owner_id=approval.approver_owner_id,
                approver_role=approval.approver_role,
                basis_ref=approval.basis_ref,
                approved_at=approval.approved_at,
            )
        )
        self._session.flush()

    # --- Approval-gated reads ------------------------------------------

    def get_published_version(self, version_id: str) -> CanonicalGraphVersion | None:
        stmt = (
            select(CanonicalGraphVersionRow)
            .join(
                EditorialApprovalRow,
                EditorialApprovalRow.graph_version_id == CanonicalGraphVersionRow.id,
            )
            .where(CanonicalGraphVersionRow.id == version_id)
        )
        row = self._session.scalars(stmt).one_or_none()
        return _version_to_domain(row) if row is not None else None

    def list_published_versions(self) -> Sequence[CanonicalGraphVersion]:
        stmt = (
            select(CanonicalGraphVersionRow)
            .join(
                EditorialApprovalRow,
                EditorialApprovalRow.graph_version_id == CanonicalGraphVersionRow.id,
            )
            .order_by(
                CanonicalGraphVersionRow.created_at.desc(),
                CanonicalGraphVersionRow.id.desc(),
            )
        )
        rows = self._session.scalars(stmt).all()
        return [_version_to_domain(row) for row in rows]

    def get_published_topics(self, version_id: str) -> Sequence[Topic]:
        stmt = (
            select(TopicRow)
            .join(
                EditorialApprovalRow,
                EditorialApprovalRow.graph_version_id == TopicRow.graph_version_id,
            )
            .where(TopicRow.graph_version_id == version_id)
        )
        rows = self._session.scalars(stmt).all()
        return [_topic_to_domain(row) for row in rows]

    def get_published_relations(self, version_id: str) -> Sequence[TopicRelation]:
        stmt = (
            select(TopicRelationRow)
            .join(
                EditorialApprovalRow,
                EditorialApprovalRow.graph_version_id
                == TopicRelationRow.graph_version_id,
            )
            .where(TopicRelationRow.graph_version_id == version_id)
        )
        rows = self._session.scalars(stmt).all()
        return [_relation_to_domain(row) for row in rows]

    def get_published_content_revisions(
        self, version_id: str, topic_stable_id: str
    ) -> Sequence[ContentRevision]:
        stmt = (
            select(ContentRevisionRow)
            .join(
                EditorialApprovalRow,
                EditorialApprovalRow.graph_version_id
                == ContentRevisionRow.graph_version_id,
            )
            .where(
                ContentRevisionRow.graph_version_id == version_id,
                ContentRevisionRow.topic_stable_id == topic_stable_id,
            )
            .order_by(ContentRevisionRow.created_at, ContentRevisionRow.id)
        )
        return [
            ContentRevision(
                id=row.id,
                graph_version_id=row.graph_version_id,
                topic_stable_id=row.topic_stable_id,
                layer=row.layer,
                kind=row.kind,
                status=row.status,
                markdown_ref=row.markdown_ref,
                markdown_hash=row.markdown_hash,
                prompt_template_version=row.prompt_template_version,
                creator_owner_id=row.creator_owner_id,
                supersedes_revision_id=row.supersedes_revision_id,
                created_at=row.created_at,
            )
            for row in self._session.scalars(stmt).all()
        ]

    # --- Pre-write lookups ----------------------------------------------

    def version_label_exists(self, version_label: str) -> bool:
        stmt = select(CanonicalGraphVersionRow.id).where(
            CanonicalGraphVersionRow.version_label == version_label
        )
        return self._session.scalars(stmt).first() is not None

    def manifest_hash_exists(self, manifest_hash: str) -> bool:
        stmt = select(CanonicalGraphVersionRow.id).where(
            CanonicalGraphVersionRow.manifest_hash == manifest_hash
        )
        return self._session.scalars(stmt).first() is not None

    def topic_identity_exists(self, stable_id: str) -> bool:
        stmt = select(TopicIdentityRow.stable_id).where(
            TopicIdentityRow.stable_id == stable_id
        )
        return self._session.scalars(stmt).first() is not None


class SqlAlchemyCanonicalMergeRepository(SqlAlchemyRepository):
    def add_merge_proposal(
        self, proposal: CanonicalMergeProposal, items: Sequence[MergeItem]
    ) -> None:
        self._session.add(
            CanonicalMergeProposalRow(
                id=proposal.id,
                owner_id=proposal.owner_id,
                goal_id=proposal.goal_id,
                base_version_id=proposal.base_version_id,
                target_version_id=proposal.target_version_id,
                goal_row_version=proposal.goal_row_version,
                diff_hash=proposal.diff_hash,
                local_state_hash=proposal.local_state_hash,
                status=proposal.status.value,
                created_at=proposal.created_at,
                decided_at=proposal.decided_at,
            )
        )
        self._session.flush()
        for item in items:
            self._session.add(
                MergeItemRow(
                    id=item.id,
                    owner_id=proposal.owner_id,
                    goal_id=proposal.goal_id,
                    proposal_id=item.proposal_id,
                    entity_type=item.entity_type.value,
                    change_type=item.change_type.value,
                    topic_id=item.topic_id,
                    title=item.title,
                    summary=item.summary,
                    impact=item.impact,
                    conflict_type=item.conflict_type,
                    selected=int(item.selected),
                    recommended_resolution=item.recommended_resolution.value,
                    chosen_resolution=item.chosen_resolution.value
                    if item.chosen_resolution
                    else None,
                    resolution_explanation=item.resolution_explanation,
                    payload_json=json.dumps(
                        item.payload, sort_keys=True, separators=(",", ":")
                    ),
                )
            )
        self._session.flush()

    def get_merge_proposal(
        self, owner_id: str, proposal_id: str
    ) -> CanonicalMergeProposal | None:
        row = self._session.scalars(
            select(CanonicalMergeProposalRow).where(
                CanonicalMergeProposalRow.owner_id == owner_id,
                CanonicalMergeProposalRow.id == proposal_id,
            )
        ).one_or_none()
        return _merge_proposal(row) if row else None

    def get_current_merge_proposal(
        self, owner_id: str, goal_id: str, base_version_id: str, target_version_id: str
    ) -> CanonicalMergeProposal | None:
        row = self._session.scalars(
            select(CanonicalMergeProposalRow)
            .where(
                CanonicalMergeProposalRow.owner_id == owner_id,
                CanonicalMergeProposalRow.goal_id == goal_id,
                CanonicalMergeProposalRow.base_version_id == base_version_id,
                CanonicalMergeProposalRow.target_version_id == target_version_id,
            )
            .order_by(
                CanonicalMergeProposalRow.created_at.desc(),
                CanonicalMergeProposalRow.id.desc(),
            )
        ).first()
        return _merge_proposal(row) if row else None

    def list_merge_items(
        self, owner_id: str, proposal_id: str
    ) -> Sequence[MergeItem]:
        return tuple(
            _merge_item(row)
            for row in self._session.scalars(
                select(MergeItemRow)
                .where(
                    MergeItemRow.owner_id == owner_id,
                    MergeItemRow.proposal_id == proposal_id,
                )
                .order_by(MergeItemRow.id)
            ).all()
        )

    def close_merge_proposal(
        self,
        owner_id: str,
        proposal_id: str,
        expected_status: str,
        status: str,
        decided_at: str,
    ) -> bool:
        result = self._session.execute(
            update(CanonicalMergeProposalRow)
            .where(
                CanonicalMergeProposalRow.owner_id == owner_id,
                CanonicalMergeProposalRow.id == proposal_id,
                CanonicalMergeProposalRow.status == expected_status,
            )
            .values(status=status, decided_at=decided_at)
        )
        self._session.flush()
        return result.rowcount == 1

    def update_merge_item(
        self,
        owner_id: str,
        proposal_id: str,
        item_id: str,
        *,
        selected: bool,
        resolution: str,
    ) -> None:
        self._session.execute(
            update(MergeItemRow)
            .where(
                MergeItemRow.owner_id == owner_id,
                MergeItemRow.proposal_id == proposal_id,
                MergeItemRow.id == item_id,
            )
            .values(selected=int(selected), chosen_resolution=resolution)
        )
        self._session.flush()

    def add_merge_followup(self, followup: CanonicalMergeFollowup) -> None:
        payload_json = json.dumps(
            followup.payload, sort_keys=True, separators=(",", ":")
        )
        from yuno.shared.domain.hashing import hash_payload

        self._session.add(
            CanonicalMergeFollowupRow(
                id=followup.id,
                owner_id=followup.owner_id,
                goal_id=followup.goal_id,
                proposal_id=followup.proposal_id,
                kind=followup.kind,
                payload_json=payload_json,
                payload_hash=hash_payload(followup.payload),
                status=followup.status,
                job_id=followup.job_id,
                created_at=followup.created_at,
            )
        )
        self._session.flush()

    def list_merge_followups(
        self, owner_id: str, proposal_id: str
    ) -> Sequence[CanonicalMergeFollowup]:
        rows = self._session.scalars(
            select(CanonicalMergeFollowupRow)
            .where(
                CanonicalMergeFollowupRow.owner_id == owner_id,
                CanonicalMergeFollowupRow.proposal_id == proposal_id,
            )
            .order_by(CanonicalMergeFollowupRow.id)
        ).all()
        return tuple(
            CanonicalMergeFollowup(
                row.id,
                row.owner_id,
                row.goal_id,
                row.proposal_id,
                row.kind,
                json.loads(row.payload_json),
                row.status,
                row.job_id,
                row.created_at,
            )
            for row in rows
        )

    def mark_followup_dispatched(
        self, owner_id: str, followup_id: str, job_id: str
    ) -> None:
        self._session.execute(
            update(CanonicalMergeFollowupRow)
            .where(
                CanonicalMergeFollowupRow.owner_id == owner_id,
                CanonicalMergeFollowupRow.id == followup_id,
                CanonicalMergeFollowupRow.status == "pending-dispatch",
            )
            .values(status="dispatched", job_id=job_id)
        )
        self._session.flush()

    def list_pending_merge_followups(self) -> Sequence[CanonicalMergeFollowup]:
        rows = self._session.scalars(
            select(CanonicalMergeFollowupRow)
            .where(CanonicalMergeFollowupRow.status == "pending-dispatch")
            .order_by(
                CanonicalMergeFollowupRow.created_at, CanonicalMergeFollowupRow.id
            )
        ).all()
        return tuple(
            CanonicalMergeFollowup(
                row.id,
                row.owner_id,
                row.goal_id,
                row.proposal_id,
                row.kind,
                json.loads(row.payload_json),
                row.status,
                row.job_id,
                row.created_at,
            )
            for row in rows
        )


def _version_to_domain(row: CanonicalGraphVersionRow) -> CanonicalGraphVersion:
    return CanonicalGraphVersion(
        id=row.id,
        version_label=row.version_label,
        manifest_version=row.manifest_version,
        manifest_hash=row.manifest_hash,
        status=CanonicalVersionStatus(row.status),
        creator_owner_id=row.creator_owner_id,
        created_at=row.created_at,
        published_at=row.published_at,
        supersedes_version_id=row.supersedes_version_id,
    )


def _topic_to_domain(row: TopicRow) -> Topic:
    return Topic(
        graph_version_id=row.graph_version_id,
        stable_id=row.stable_id,
        title=row.title,
        subject=row.subject,
        scope_tags=tuple(json.loads(row.scope_tags)),
        level_tag=row.level_tag,
        target_capability=row.target_capability,
        recommended_layer=row.recommended_layer,
        checkpoint_start=row.checkpoint_start,
        checkpoint_end=row.checkpoint_end,
    )


def _relation_to_domain(row: TopicRelationRow) -> TopicRelation:
    return TopicRelation(
        id=row.id,
        graph_version_id=row.graph_version_id,
        from_stable_id=row.from_stable_id,
        to_stable_id=row.to_stable_id,
        relation_type=RelationType(row.relation_type),
        rationale=row.rationale,
    )


def _merge_proposal(row: CanonicalMergeProposalRow) -> CanonicalMergeProposal:
    return CanonicalMergeProposal(
        row.id,
        row.owner_id,
        row.goal_id,
        row.base_version_id,
        row.target_version_id,
        row.goal_row_version,
        row.diff_hash,
        row.local_state_hash,
        MergeProposalStatus(row.status),
        row.created_at,
        row.decided_at,
    )


def _merge_item(row: MergeItemRow) -> MergeItem:
    return MergeItem(
        row.id,
        row.proposal_id,
        MergeEntityType(row.entity_type),
        MergeChangeType(row.change_type),
        row.topic_id,
        row.title,
        row.summary,
        row.impact,
        row.conflict_type,
        bool(row.selected),
        MergeResolution(row.recommended_resolution),
        MergeResolution(row.chosen_resolution) if row.chosen_resolution else None,
        row.resolution_explanation,
        json.loads(row.payload_json),
    )

"""Owner-scoped SQLAlchemy source registry."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from yuno.modules.provenance.domain import (
    ArtifactProvenanceRef,
    ArtifactProvenanceSnapshot,
    Citation,
    Claim,
    ClaimStatus,
    ClaimType,
    Source,
    SourceAvailability,
    SourceRetrievalCommand,
    SourceSnapshot,
)
from yuno.modules.provenance.models import (
    ArtifactProvenanceRefRow,
    ArtifactProvenanceSnapshotRow,
    CitationBodyRow,
    CitationRow,
    ClaimBodyRow,
    ClaimRow,
    SourceBodyRow,
    SourceRetrievalCommandRow,
    SourceRow,
    SourceSnapshotBodyRow,
    SourceSnapshotRow,
)
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemySourceRepository(SqlAlchemyRepository):
    def add_source(self, source: Source) -> Source:
        values = source.__dict__.copy()
        body = {key: values.pop(key) for key in ("title", "publisher", "canonical_url")}
        values["availability_status"] = source.availability_status.value
        values["body_hash"] = _body_hash(**body)
        self._session.add(SourceRow(**values))
        self._session.flush()
        self._session.add(
            SourceBodyRow(source_id=source.id, owner_id=source.owner_id, **body)
        )
        return source

    def get_source(self, owner_id: str, source_id: str) -> Source | None:
        row = self._session.scalars(
            owner_scoped_select(SourceRow, owner_id).where(SourceRow.id == source_id)
        ).one_or_none()
        return _source(row) if row else None

    def list_sources(self, owner_id: str) -> Sequence[Source]:
        rows = (
            self._session.scalars(
                owner_scoped_select(SourceRow, owner_id)
                .join(SourceBodyRow, SourceBodyRow.source_id == SourceRow.id)
                .order_by(SourceBodyRow.title, SourceRow.id)
            )
            .unique()
            .all()
        )
        return tuple(item for row in rows if (item := _source(row)) is not None)

    def get_source_snapshot(self, owner_id, snapshot_id):
        r = self._session.scalars(
            owner_scoped_select(SourceSnapshotRow, owner_id).where(
                SourceSnapshotRow.id == snapshot_id
            )
        ).one_or_none()
        return (
            SourceSnapshot(
                r.id,
                r.owner_id,
                r.source_id,
                r.retrieved_at,
                r.body.content_ref,
                r.content_hash,
                r.status,
                r.body.version_label,
            )
            if r and r.body
            else None
        )

    def add_source_snapshot(self, snapshot):
        values = snapshot.__dict__.copy()
        body = {key: values.pop(key) for key in ("content_ref", "version_label")}
        self._session.add(SourceSnapshotRow(**values))
        self._session.flush()
        self._session.add(
            SourceSnapshotBodyRow(
                snapshot_id=snapshot.id,
                owner_id=snapshot.owner_id,
                source_id=snapshot.source_id,
                redacted_failure=None,
                **body,
            )
        )
        return snapshot

    def list_source_snapshots(self, owner_id, source_id):
        rows = self._session.scalars(
            owner_scoped_select(SourceSnapshotRow, owner_id)
            .where(SourceSnapshotRow.source_id == source_id)
            .order_by(
                SourceSnapshotRow.retrieved_at.desc(), SourceSnapshotRow.id.desc()
            )
        ).all()
        return tuple(
            item for row in rows if (item := _source_snapshot(row)) is not None
        )

    def add_retrieval_command(self, command):
        self._session.add(SourceRetrievalCommandRow(**command.__dict__))
        self._session.flush()
        return command

    def get_retrieval_command_by_idempotency(self, owner_id, key):
        row = self._session.scalars(
            owner_scoped_select(SourceRetrievalCommandRow, owner_id).where(
                SourceRetrievalCommandRow.idempotency_key == key
            )
        ).one_or_none()
        return (
            SourceRetrievalCommand(
                row.id,
                row.owner_id,
                row.source_id,
                row.job_id,
                row.idempotency_key,
                row.request_hash,
                row.created_at,
            )
            if row
            else None
        )

    def add_generation_result(self, snapshot, refs, claims):
        self._session.add(ArtifactProvenanceSnapshotRow(**snapshot.__dict__))
        self._session.flush()
        for ref in refs:
            self._session.add(ArtifactProvenanceRefRow(**ref.__dict__))
        for claim, citations in claims:
            values = claim.__dict__.copy()
            claim_text = values.pop("claim_text")
            values.update(
                claim_type=getattr(claim.claim_type, "value", claim.claim_type),
                status=ClaimStatus.PENDING.value,
                sensitive=int(claim.sensitive),
                claim_hash=_body_hash(claim_text=claim_text),
            )
            self._session.add(ClaimRow(**values))
            self._session.flush()
            self._session.add(
                ClaimBodyRow(
                    claim_id=claim.id,
                    owner_id=claim.owner_id,
                    goal_id=claim.goal_id,
                    claim_text=claim_text,
                )
            )
            for citation in citations:
                citation_values = citation.__dict__.copy()
                citation_body = {
                    key: citation_values.pop(key) for key in ("locator", "note")
                }
                citation_values["body_hash"] = _body_hash(**citation_body)
                self._session.add(CitationRow(**citation_values))
                self._session.flush()
                self._session.add(
                    CitationBodyRow(
                        citation_id=citation.id,
                        owner_id=citation.owner_id,
                        goal_id=citation.goal_id,
                        **citation_body,
                    )
                )
            self._session.flush()
            claim_row = self._session.get(ClaimRow, claim.id)
            claim_row.status = ClaimStatus.PUBLISHED.value
        self._session.flush()

    def get_artifact_snapshot(self, owner_id, snapshot_id):
        r = self._session.scalars(
            owner_scoped_select(ArtifactProvenanceSnapshotRow, owner_id).where(
                ArtifactProvenanceSnapshotRow.id == snapshot_id
            )
        ).one_or_none()
        return _snapshot(r) if r else None

    def list_artifact_refs(self, owner_id, snapshot_id):
        rows = self._session.scalars(
            owner_scoped_select(ArtifactProvenanceRefRow, owner_id).where(
                ArtifactProvenanceRefRow.snapshot_id == snapshot_id
            )
        ).all()
        return tuple(
            ArtifactProvenanceRef(
                r.id,
                r.owner_id,
                r.goal_id,
                r.artifact_id,
                r.snapshot_id,
                r.ref_kind,
                r.reference_id,
            )
            for r in rows
        )

    def get_claim(self, owner_id, claim_id):
        r = self._session.scalars(
            owner_scoped_select(ClaimRow, owner_id).where(
                ClaimRow.id == claim_id, ClaimRow.status == "published"
            )
        ).one_or_none()
        return _claim(r) if r and r.body else None

    def list_claims(self, owner_id, snapshot_id):
        rows = self._session.scalars(
            owner_scoped_select(ClaimRow, owner_id).where(
                ClaimRow.snapshot_id == snapshot_id, ClaimRow.status == "published"
            )
        ).all()
        return tuple(item for r in rows if (item := _claim(r)) is not None)

    def list_citations(self, owner_id, claim_id):
        rows = self._session.scalars(
            owner_scoped_select(CitationRow, owner_id).where(
                CitationRow.claim_id == claim_id
            )
        ).all()
        return tuple(
            Citation(
                r.id,
                r.owner_id,
                r.goal_id,
                r.claim_id,
                r.source_id,
                r.source_snapshot_id,
                r.body.locator,
                r.support_kind,
                r.body.note,
            )
            for r in rows
            if r.body is not None
        )


def _source(row: SourceRow) -> Source | None:
    if row.body is None:
        return None
    return Source(
        row.id,
        row.owner_id,
        row.origin,
        row.source_type,
        row.body.title,
        row.body.publisher,
        row.body.canonical_url,
        row.license_status,
        SourceAvailability(row.availability_status),
        row.created_at,
        row.updated_at,
    )


def _source_snapshot(row: SourceSnapshotRow) -> SourceSnapshot | None:
    if row.body is None:
        return None
    return SourceSnapshot(
        row.id,
        row.owner_id,
        row.source_id,
        row.retrieved_at,
        row.body.content_ref,
        row.content_hash,
        row.status,
        row.body.version_label,
    )


def _snapshot(r):
    return ArtifactProvenanceSnapshot(
        r.id,
        r.owner_id,
        r.goal_id,
        r.artifact_id,
        r.attempt_id,
        r.evidence_state_hash,
        r.profile_hash,
        r.provider,
        r.model,
        r.generated_at,
        r.schema_version,
        r.contract_version,
        r.prompt_template_version,
        r.snapshot_hash,
    )


def _claim(r):
    if r.body is None:
        return None
    return Claim(
        r.id,
        r.owner_id,
        r.goal_id,
        r.content_revision_id,
        r.generated_artifact_id,
        r.snapshot_id,
        r.body.claim_text,
        ClaimType(r.claim_type),
        bool(r.sensitive),
        ClaimStatus(r.status),
    )


def _body_hash(**values: object) -> str:
    encoded = json.dumps(
        values, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

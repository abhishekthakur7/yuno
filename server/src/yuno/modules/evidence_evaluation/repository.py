"""SQLAlchemy evidence repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete

from yuno.modules.evidence_evaluation.domain import (
    Evidence,
    EvidenceDeleteSnapshot,
    EvidencePayload,
    EvidenceTombstone,
)
from yuno.modules.evidence_evaluation.models import (
    EvidenceDeleteSnapshotRow,
    EvidencePayloadRow,
    EvidenceRow,
    EvidenceTombstoneRow,
)
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyEvidenceRepository(SqlAlchemyRepository):
    def add_evidence(self, evidence: Evidence, payload: EvidencePayload) -> Evidence:
        self._session.add(EvidenceRow(**evidence.__dict__))
        self._session.flush()
        self._session.add(EvidencePayloadRow(**payload.__dict__))
        self._session.flush()
        return evidence

    def get_evidence(
        self, owner_id: str, goal_id: str, evidence_id: str
    ) -> Evidence | None:
        row = self._session.scalars(
            owner_scoped_select(EvidenceRow, owner_id).where(
                EvidenceRow.goal_id == goal_id, EvidenceRow.id == evidence_id
            )
        ).one_or_none()
        return _evidence(row) if row else None

    def get_payload(
        self, owner_id: str, goal_id: str, evidence_id: str
    ) -> EvidencePayload | None:
        row = self._session.scalars(
            owner_scoped_select(EvidencePayloadRow, owner_id).where(
                EvidencePayloadRow.goal_id == goal_id,
                EvidencePayloadRow.evidence_id == evidence_id,
            )
        ).one_or_none()
        return _payload(row) if row else None

    def list_evidence(self, owner_id: str, goal_id: str) -> Sequence[Evidence]:
        rows = self._session.scalars(
            owner_scoped_select(EvidenceRow, owner_id)
            .where(EvidenceRow.goal_id == goal_id)
            .order_by(EvidenceRow.id)
        ).all()
        return tuple(_evidence(row) for row in rows)

    def add_tombstone(self, tombstone: EvidenceTombstone) -> None:
        self._session.add(EvidenceTombstoneRow(**tombstone.__dict__))
        self._session.flush()

    def remove_payload(self, owner_id: str, goal_id: str, evidence_id: str) -> None:
        self._session.execute(
            delete(EvidencePayloadRow).where(
                EvidencePayloadRow.owner_id == owner_id,
                EvidencePayloadRow.goal_id == goal_id,
                EvidencePayloadRow.evidence_id == evidence_id,
            )
        )
        self._session.flush()

    def list_tombstones(
        self, owner_id: str, goal_id: str
    ) -> Sequence[EvidenceTombstone]:
        rows = self._session.scalars(
            owner_scoped_select(EvidenceTombstoneRow, owner_id)
            .where(EvidenceTombstoneRow.goal_id == goal_id)
            .order_by(EvidenceTombstoneRow.evidence_id)
        ).all()
        return tuple(_tombstone(row) for row in rows)

    def add_delete_snapshot(self, snapshot: EvidenceDeleteSnapshot) -> None:
        self._session.add(EvidenceDeleteSnapshotRow(**snapshot.__dict__))
        self._session.flush()

    def get_delete_snapshot(
        self, owner_id: str, goal_id: str, snapshot_id: str
    ) -> EvidenceDeleteSnapshot | None:
        row = self._session.scalars(
            owner_scoped_select(EvidenceDeleteSnapshotRow, owner_id).where(
                EvidenceDeleteSnapshotRow.goal_id == goal_id,
                EvidenceDeleteSnapshotRow.id == snapshot_id,
            )
        ).one_or_none()
        if row is None:
            return None
        return EvidenceDeleteSnapshot(
            row.id,
            row.owner_id,
            row.goal_id,
            row.impact_json,
            row.impact_hash,
            row.created_at,
        )


def _evidence(row: EvidenceRow) -> Evidence:
    return Evidence(
        row.id,
        row.owner_id,
        row.goal_id,
        row.topic_stable_id,
        row.evidence_type,
        row.capability,
        row.payload_hash,
        row.summary,
        row.origin,
        row.created_at,
    )


def _payload(row: EvidencePayloadRow) -> EvidencePayload:
    return EvidencePayload(
        row.evidence_id, row.owner_id, row.goal_id, row.content, row.content_version
    )


def _tombstone(row: EvidenceTombstoneRow) -> EvidenceTombstone:
    return EvidenceTombstone(
        row.evidence_id,
        row.owner_id,
        row.goal_id,
        row.delete_operation_id,
        row.reason,
        row.tombstoned_at,
    )

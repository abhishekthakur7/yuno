"""Owner-scoped SQLAlchemy roadmap repository."""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from yuno.modules.roadmap.domain import (
    CorrectionType,
    LearnerCorrection,
    LearningClassification,
    LearningState,
    OverlayEntry,
    OverlayEntryType,
    PersonalOverlay,
    RoadmapIdempotencyRecord,
)
from yuno.modules.roadmap.models import (
    LearnerCorrectionRow,
    LearningStateRow,
    OverlayEntryRow,
    PersonalOverlayRow,
    RoadmapIdempotencyRow,
    TransferredEvidenceRefRow,
)
from yuno.modules.roadmap.ports import (
    TransferEvidenceRefView,
    TransferLearningStateView,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyRoadmapRepository(SqlAlchemyRepository):
    __slots__ = ("_clock",)

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._clock = SystemClock()

    def get_or_create_overlay(
        self, owner_id: str, goal_id: str, graph_version_id: str
    ) -> PersonalOverlay:
        existing = self.get_overlay(owner_id, goal_id)
        if existing is not None:
            return existing
        row = PersonalOverlayRow(
            id=new_id(),
            owner_id=owner_id,
            goal_id=goal_id,
            base_graph_version_id=graph_version_id,
            state="active",
            row_version=1,
            created_at=now_text(self._clock),
        )
        self._session.add(row)
        self._session.flush()
        return _overlay(row)

    def get_overlay(self, owner_id: str, goal_id: str) -> PersonalOverlay | None:
        row = self._session.scalars(
            owner_scoped_select(PersonalOverlayRow, owner_id).where(
                PersonalOverlayRow.goal_id == goal_id
            )
        ).one_or_none()
        return _overlay(row) if row else None

    def append_overlay_entry(self, entry: OverlayEntry) -> OverlayEntry:
        self._session.add(
            OverlayEntryRow(
                id=entry.id,
                owner_id=entry.owner_id,
                goal_id=entry.goal_id,
                overlay_id=entry.overlay_id,
                graph_version_id=entry.graph_version_id,
                topic_stable_id=entry.topic_stable_id,
                entry_type=entry.entry_type.value,
                value_json=json.dumps(
                    entry.value, sort_keys=True, separators=(",", ":")
                ),
                reason=entry.reason,
                source=entry.source,
                approved_at=entry.approved_at,
                supersedes_entry_id=entry.supersedes_entry_id,
                content_hash=entry.content_hash,
            )
        )
        self._session.flush()
        return entry

    def list_overlay_entries(
        self, owner_id: str, goal_id: str
    ) -> Sequence[OverlayEntry]:
        rows = self._session.scalars(
            owner_scoped_select(OverlayEntryRow, owner_id)
            .where(OverlayEntryRow.goal_id == goal_id)
            .order_by(OverlayEntryRow.approved_at, OverlayEntryRow.id)
        ).all()
        return tuple(_entry(row) for row in rows)

    def add_learning_state(self, state: LearningState) -> LearningState:
        self._session.add(
            LearningStateRow(
                id=state.id,
                owner_id=state.owner_id,
                goal_id=state.goal_id,
                topic_stable_id=state.topic_stable_id,
                graph_version_id=state.graph_version_id,
                classification=state.classification.value,
                origin=state.origin,
                recommended_depth=state.recommended_depth,
                explanation=state.explanation,
                derivation_version=state.derivation_version,
                input_hash=state.input_hash,
                derived_at=state.derived_at,
            )
        )
        self._session.flush()
        return state

    def list_learning_states(
        self, owner_id: str, goal_id: str
    ) -> Sequence[LearningState]:
        rows = self._session.scalars(
            owner_scoped_select(LearningStateRow, owner_id)
            .where(LearningStateRow.goal_id == goal_id)
            .order_by(LearningStateRow.topic_stable_id)
        ).all()
        return tuple(_state(row) for row in rows)

    def append_correction(self, correction: LearnerCorrection) -> LearnerCorrection:
        self._session.add(
            LearnerCorrectionRow(
                id=correction.id,
                owner_id=correction.owner_id,
                goal_id=correction.goal_id,
                topic_stable_id=correction.topic_stable_id,
                correction_type=correction.correction_type.value,
                value=correction.value,
                reason=correction.reason,
                created_at=correction.created_at,
                supersedes_correction_id=correction.supersedes_correction_id,
            )
        )
        self._session.flush()
        return correction

    def list_corrections(
        self, owner_id: str, goal_id: str
    ) -> Sequence[LearnerCorrection]:
        rows = self._session.scalars(
            owner_scoped_select(LearnerCorrectionRow, owner_id)
            .where(LearnerCorrectionRow.goal_id == goal_id)
            .order_by(LearnerCorrectionRow.created_at, LearnerCorrectionRow.id)
        ).all()
        return tuple(_correction(row) for row in rows)

    def list_transferred_evidence_topic_ids(
        self, owner_id: str, goal_id: str
    ) -> Sequence[str]:
        stmt = (
            select(LearningStateRow.topic_stable_id)
            .join(
                TransferredEvidenceRefRow,
                TransferredEvidenceRefRow.learning_state_id == LearningStateRow.id,
            )
            .where(
                LearningStateRow.owner_id == owner_id,
                LearningStateRow.goal_id == goal_id,
            )
            .distinct()
            .order_by(LearningStateRow.topic_stable_id)
        )
        return tuple(self._session.scalars(stmt).all())

    def get_learning_state_for_topic(
        self, owner_id: str, goal_id: str, topic_stable_id: str
    ) -> LearningState | None:
        row = self._session.scalars(
            owner_scoped_select(LearningStateRow, owner_id).where(
                LearningStateRow.goal_id == goal_id,
                LearningStateRow.topic_stable_id == topic_stable_id,
            )
        ).one_or_none()
        return _state(row) if row else None

    def add_transferred_evidence(
        self,
        learning_state: TransferLearningStateView,
        transfer_ref: TransferEvidenceRefView,
    ) -> None:
        self._session.add(
            LearningStateRow(
                id=learning_state.id,
                owner_id=learning_state.owner_id,
                goal_id=learning_state.goal_id,
                topic_stable_id=learning_state.topic_stable_id,
                graph_version_id=learning_state.graph_version_id,
                classification=learning_state.classification.value,
                origin=learning_state.origin,
                recommended_depth=learning_state.recommended_depth,
                explanation=learning_state.explanation,
                derivation_version=learning_state.derivation_version,
                input_hash=learning_state.input_hash,
                derived_at=learning_state.derived_at,
            )
        )
        self._session.add(
            TransferredEvidenceRefRow(
                id=transfer_ref.id,
                owner_id=transfer_ref.owner_id,
                goal_id=transfer_ref.goal_id,
                learning_state_id=transfer_ref.learning_state_id,
                source_goal_id=transfer_ref.source_goal_id,
                source_evidence_id=transfer_ref.source_evidence_id,
                classification=transfer_ref.classification.value,
                rationale=transfer_ref.rationale,
                created_at=transfer_ref.created_at,
            )
        )
        self._session.flush()

    def list_transfer_dependents(
        self, owner_id: str, source_goal_id: str
    ) -> Sequence[tuple[str, str]]:
        stmt = (
            select(
                TransferredEvidenceRefRow.source_evidence_id,
                TransferredEvidenceRefRow.learning_state_id,
            )
            .where(
                TransferredEvidenceRefRow.owner_id == owner_id,
                TransferredEvidenceRefRow.source_goal_id == source_goal_id,
            )
            .order_by(
                TransferredEvidenceRefRow.source_evidence_id,
                TransferredEvidenceRefRow.learning_state_id,
            )
        )
        return tuple(self._session.execute(stmt).tuples().all())

    def downgrade_transfer_dependents(
        self, owner_id: str, source_goal_id: str, *, derived_at: str
    ) -> None:
        state_ids = select(TransferredEvidenceRefRow.learning_state_id).where(
            TransferredEvidenceRefRow.owner_id == owner_id,
            TransferredEvidenceRefRow.source_goal_id == source_goal_id,
        )
        self._session.execute(
            update(LearningStateRow)
            .where(
                LearningStateRow.owner_id == owner_id,
                LearningStateRow.id.in_(state_ids),
            )
            .values(
                classification="unverified",
                origin="tombstoned-transfer",
                explanation="The source evidence was tombstoned when its goal was deleted.",
                derivation_version="transfer-tombstone-v1",
                input_hash="tombstoned",
                derived_at=derived_at,
            )
        )
        self._session.flush()

    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> RoadmapIdempotencyRecord | None:
        row = self._session.scalars(
            owner_scoped_select(RoadmapIdempotencyRow, owner_id).where(
                RoadmapIdempotencyRow.operation == operation,
                RoadmapIdempotencyRow.idempotency_key == key,
            )
        ).one_or_none()
        if row is None:
            return None
        return RoadmapIdempotencyRecord(
            id=row.id,
            owner_id=row.owner_id,
            goal_id=row.goal_id,
            operation=row.operation,
            idempotency_key=row.idempotency_key,
            request_hash=row.request_hash,
            response_json=row.response_json,
            created_at=row.created_at,
        )

    def add_idempotency(self, record: RoadmapIdempotencyRecord) -> None:
        self._session.add(
            RoadmapIdempotencyRow(
                id=record.id,
                owner_id=record.owner_id,
                goal_id=record.goal_id,
                operation=record.operation,
                idempotency_key=record.idempotency_key,
                request_hash=record.request_hash,
                response_json=record.response_json,
                created_at=record.created_at,
            )
        )
        self._session.flush()


def _overlay(row: PersonalOverlayRow) -> PersonalOverlay:
    return PersonalOverlay(
        row.id,
        row.owner_id,
        row.goal_id,
        row.base_graph_version_id,
        row.state,
        row.row_version,
        row.created_at,
    )


def _entry(row: OverlayEntryRow) -> OverlayEntry:
    return OverlayEntry(
        row.id,
        row.owner_id,
        row.goal_id,
        row.overlay_id,
        row.graph_version_id,
        row.topic_stable_id,
        OverlayEntryType(row.entry_type),
        json.loads(row.value_json),
        row.reason,
        row.source,
        row.approved_at,
        row.supersedes_entry_id,
        row.content_hash,
    )


def _state(row: LearningStateRow) -> LearningState:
    return LearningState(
        row.id,
        row.owner_id,
        row.goal_id,
        row.topic_stable_id,
        row.graph_version_id,
        LearningClassification(row.classification),
        row.origin,
        row.recommended_depth,
        row.explanation,
        row.derivation_version,
        row.input_hash,
        row.derived_at,
    )


def _correction(row: LearnerCorrectionRow) -> LearnerCorrection:
    return LearnerCorrection(
        row.id,
        row.owner_id,
        row.goal_id,
        row.topic_stable_id,
        CorrectionType(row.correction_type),
        row.value,
        row.reason,
        row.created_at,
        row.supersedes_correction_id,
    )

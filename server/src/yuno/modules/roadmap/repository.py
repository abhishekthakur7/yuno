"""Owner-scoped SQLAlchemy roadmap repository."""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from yuno.modules.data_lifecycle.models import (
    LearnerCorrectionBodyRow,
    LearningStateBodyRow,
    OverlayEntryBodyRow,
    OverlayProposalBodyRow,
    OverlayProposalDecisionBodyRow,
    RoadmapIdempotencyBodyRow,
    TransferredEvidenceRefBodyRow,
)
from yuno.modules.roadmap.domain import (
    CorrectionType,
    LearnerCorrection,
    LearningClassification,
    LearningState,
    OverlayDecisionType,
    OverlayEntry,
    OverlayEntryType,
    OverlayProposal,
    OverlayProposalDecision,
    OverlayProposalState,
    OverlayProposalType,
    PersonalOverlay,
    RoadmapIdempotencyRecord,
)
from yuno.modules.roadmap.models import (
    LearnerCorrectionRow,
    LearningStateRow,
    OverlayEntryRow,
    OverlayProposalDecisionRow,
    OverlayProposalRow,
    PersonalOverlayRow,
    RoadmapIdempotencyRow,
    TransferredEvidenceRefRow,
)
from yuno.modules.roadmap.ports import (
    EvidenceTransferView,
    ProgressTransferView,
    TransferEvidenceRefView,
    TransferLearningStateView,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.hashing import hash_payload
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

    def advance_overlay_base(
        self, owner_id: str, goal_id: str, expected_version: int, graph_version_id: str
    ) -> PersonalOverlay | None:
        result = self._session.execute(
            update(PersonalOverlayRow)
            .where(
                PersonalOverlayRow.owner_id == owner_id,
                PersonalOverlayRow.goal_id == goal_id,
                PersonalOverlayRow.row_version == expected_version,
            )
            .values(
                base_graph_version_id=graph_version_id, row_version=expected_version + 1
            )
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        return self.get_overlay(owner_id, goal_id)

    def append_overlay_entry(self, entry: OverlayEntry) -> OverlayEntry:
        row = OverlayEntryRow(
            id=entry.id,
            owner_id=entry.owner_id,
            goal_id=entry.goal_id,
            overlay_id=entry.overlay_id,
            graph_version_id=entry.graph_version_id,
            topic_stable_id=entry.topic_stable_id,
            entry_type=entry.entry_type.value,
            source=entry.source,
            approved_at=entry.approved_at,
            supersedes_entry_id=entry.supersedes_entry_id,
            content_hash=entry.content_hash,
        )
        self._session.add(row)
        self._session.flush()
        self._session.add(
            OverlayEntryBodyRow(
                entry_id=entry.id,
                owner_id=entry.owner_id,
                goal_id=entry.goal_id,
                value_json=json.dumps(
                    entry.value, sort_keys=True, separators=(",", ":")
                ),
                reason=entry.reason,
            )
        )
        self._session.flush()
        return entry

    def list_overlay_entries(
        self, owner_id: str, goal_id: str
    ) -> Sequence[OverlayEntry]:
        rows = self._session.execute(
            select(OverlayEntryRow, OverlayEntryBodyRow)
            .join(
                OverlayEntryBodyRow, OverlayEntryBodyRow.entry_id == OverlayEntryRow.id
            )
            .where(OverlayEntryRow.owner_id == owner_id)
            .where(OverlayEntryRow.goal_id == goal_id)
            .order_by(OverlayEntryRow.approved_at, OverlayEntryRow.id)
        ).all()
        return tuple(_entry(row, body) for row, body in rows)

    def add_proposal(self, proposal: OverlayProposal) -> OverlayProposal:
        row = OverlayProposalRow(
            id=proposal.id,
            owner_id=proposal.owner_id,
            goal_id=proposal.goal_id,
            generated_against_graph_version_id=proposal.generated_against_graph_version_id,
            topic_stable_id=proposal.topic_stable_id,
            proposal_type=proposal.proposal_type.value,
            content_hash=proposal.content_hash,
            state=proposal.state.value,
            created_at=proposal.created_at,
            decided_at=proposal.decided_at,
        )
        self._session.add(row)
        self._session.flush()
        self._session.add(
            OverlayProposalBodyRow(
                proposal_id=proposal.id,
                owner_id=proposal.owner_id,
                goal_id=proposal.goal_id,
                payload_json=json.dumps(
                    proposal.payload, sort_keys=True, separators=(",", ":")
                ),
                state_reason=proposal.state_reason,
            )
        )
        self._session.flush()
        return proposal

    def get_proposal(self, owner_id: str, proposal_id: str) -> OverlayProposal | None:
        pair = self._session.execute(
            select(OverlayProposalRow, OverlayProposalBodyRow)
            .join(
                OverlayProposalBodyRow,
                OverlayProposalBodyRow.proposal_id == OverlayProposalRow.id,
            )
            .where(
                OverlayProposalRow.owner_id == owner_id,
                OverlayProposalRow.id == proposal_id,
            )
        ).one_or_none()
        return _proposal(*pair) if pair else None

    def get_pending_proposal_by_hash(
        self, owner_id: str, goal_id: str, content_hash: str
    ) -> OverlayProposal | None:
        pair = self._session.execute(
            select(OverlayProposalRow, OverlayProposalBodyRow)
            .join(
                OverlayProposalBodyRow,
                OverlayProposalBodyRow.proposal_id == OverlayProposalRow.id,
            )
            .where(
                OverlayProposalRow.owner_id == owner_id,
                OverlayProposalRow.goal_id == goal_id,
                OverlayProposalRow.content_hash == content_hash,
                OverlayProposalRow.state
                == OverlayProposalState.AWAITING_DECISION.value,
            )
        ).one_or_none()
        return _proposal(*pair) if pair else None

    def list_proposals(self, owner_id: str, goal_id: str) -> Sequence[OverlayProposal]:
        rows = self._session.execute(
            select(OverlayProposalRow, OverlayProposalBodyRow)
            .join(
                OverlayProposalBodyRow,
                OverlayProposalBodyRow.proposal_id == OverlayProposalRow.id,
            )
            .where(OverlayProposalRow.owner_id == owner_id)
            .where(OverlayProposalRow.goal_id == goal_id)
            .order_by(OverlayProposalRow.created_at, OverlayProposalRow.id)
        ).all()
        return tuple(_proposal(row, body) for row, body in rows)

    def count_pending_proposals(self, owner_id: str, goal_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(OverlayProposalRow)
                .where(
                    OverlayProposalRow.owner_id == owner_id,
                    OverlayProposalRow.goal_id == goal_id,
                    OverlayProposalRow.state
                    == OverlayProposalState.AWAITING_DECISION.value,
                )
            )
            or 0
        )

    def update_proposal_state(
        self,
        owner_id: str,
        proposal_id: str,
        expected_state: str,
        *,
        state: str,
        state_reason: str | None,
        decided_at: str,
    ) -> OverlayProposal | None:
        result = self._session.execute(
            update(OverlayProposalRow)
            .where(
                OverlayProposalRow.owner_id == owner_id,
                OverlayProposalRow.id == proposal_id,
                OverlayProposalRow.state == expected_state,
            )
            .values(state=state, decided_at=decided_at)
        )
        if result.rowcount != 1:
            return None
        self._session.execute(
            update(OverlayProposalBodyRow)
            .where(
                OverlayProposalBodyRow.owner_id == owner_id,
                OverlayProposalBodyRow.proposal_id == proposal_id,
            )
            .values(state_reason=state_reason)
        )
        self._session.flush()
        return self.get_proposal(owner_id, proposal_id)

    def append_proposal_decision(
        self, decision: OverlayProposalDecision
    ) -> OverlayProposalDecision:
        row = OverlayProposalDecisionRow(
            id=decision.id,
            owner_id=decision.owner_id,
            goal_id=decision.goal_id,
            proposal_id=decision.proposal_id,
            decision=decision.decision.value,
            body_hash=hash_payload(decision.reason),
            decided_at=decision.decided_at,
        )
        self._session.add(row)
        self._session.flush()
        self._session.add(
            OverlayProposalDecisionBodyRow(
                decision_id=decision.id,
                owner_id=decision.owner_id,
                goal_id=decision.goal_id,
                reason=decision.reason,
            )
        )
        self._session.flush()
        return decision

    def list_proposal_decisions(
        self, owner_id: str, proposal_id: str
    ) -> Sequence[OverlayProposalDecision]:
        rows = self._session.execute(
            select(OverlayProposalDecisionRow, OverlayProposalDecisionBodyRow)
            .join(
                OverlayProposalDecisionBodyRow,
                OverlayProposalDecisionBodyRow.decision_id
                == OverlayProposalDecisionRow.id,
            )
            .where(OverlayProposalDecisionRow.owner_id == owner_id)
            .where(OverlayProposalDecisionRow.proposal_id == proposal_id)
            .order_by(
                OverlayProposalDecisionRow.decided_at,
                OverlayProposalDecisionRow.id,
            )
        ).all()
        return tuple(_proposal_decision(row, body) for row, body in rows)

    def add_learning_state(self, state: LearningState) -> LearningState:
        row = LearningStateRow(
            id=state.id,
            owner_id=state.owner_id,
            goal_id=state.goal_id,
            topic_stable_id=state.topic_stable_id,
            graph_version_id=state.graph_version_id,
            classification=state.classification.value,
            origin=state.origin,
            recommended_depth=state.recommended_depth,
            body_hash=hash_payload(state.explanation),
            derivation_version=state.derivation_version,
            input_hash=state.input_hash,
            derived_at=state.derived_at,
        )
        self._session.add(row)
        self._session.flush()
        self._session.add(
            LearningStateBodyRow(
                state_id=state.id,
                owner_id=state.owner_id,
                goal_id=state.goal_id,
                explanation=state.explanation,
            )
        )
        self._session.flush()
        return state

    def list_learning_states(
        self, owner_id: str, goal_id: str
    ) -> Sequence[LearningState]:
        rows = self._session.execute(
            select(LearningStateRow, LearningStateBodyRow)
            .join(
                LearningStateBodyRow,
                LearningStateBodyRow.state_id == LearningStateRow.id,
            )
            .where(LearningStateRow.owner_id == owner_id)
            .where(LearningStateRow.goal_id == goal_id)
            .order_by(LearningStateRow.topic_stable_id)
        ).all()
        return tuple(_state(row, body) for row, body in rows)

    def append_correction(self, correction: LearnerCorrection) -> LearnerCorrection:
        row = LearnerCorrectionRow(
            id=correction.id,
            owner_id=correction.owner_id,
            goal_id=correction.goal_id,
            topic_stable_id=correction.topic_stable_id,
            correction_type=correction.correction_type.value,
            body_hash=hash_payload(
                {"value": correction.value, "reason": correction.reason}
            ),
            created_at=correction.created_at,
            supersedes_correction_id=correction.supersedes_correction_id,
        )
        self._session.add(row)
        self._session.flush()
        self._session.add(
            LearnerCorrectionBodyRow(
                correction_id=correction.id,
                owner_id=correction.owner_id,
                goal_id=correction.goal_id,
                value=correction.value,
                reason=correction.reason,
            )
        )
        self._session.flush()
        return correction

    def list_corrections(
        self, owner_id: str, goal_id: str
    ) -> Sequence[LearnerCorrection]:
        rows = self._session.execute(
            select(LearnerCorrectionRow, LearnerCorrectionBodyRow)
            .join(
                LearnerCorrectionBodyRow,
                LearnerCorrectionBodyRow.correction_id == LearnerCorrectionRow.id,
            )
            .where(LearnerCorrectionRow.owner_id == owner_id)
            .where(LearnerCorrectionRow.goal_id == goal_id)
            .order_by(LearnerCorrectionRow.created_at, LearnerCorrectionRow.id)
        ).all()
        return tuple(_correction(row, body) for row, body in rows)

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

    def list_progress_transfers(self, owner_id: str, goal_id: str):
        stmt = (
            select(
                TransferredEvidenceRefRow,
                TransferredEvidenceRefBodyRow,
                LearningStateRow.topic_stable_id,
                LearningStateRow.classification,
            )
            .join(
                TransferredEvidenceRefBodyRow,
                TransferredEvidenceRefBodyRow.transfer_id
                == TransferredEvidenceRefRow.id,
            )
            .join(
                LearningStateRow,
                LearningStateRow.id == TransferredEvidenceRefRow.learning_state_id,
            )
            .where(
                TransferredEvidenceRefRow.owner_id == owner_id,
                TransferredEvidenceRefRow.goal_id == goal_id,
            )
            .order_by(TransferredEvidenceRefRow.id)
        )
        return tuple(
            ProgressTransferView(
                row.id,
                row.owner_id,
                row.goal_id,
                topic,
                row.source_evidence_id,
                classification,
                body.rationale,
                row.created_at,
            )
            for row, body, topic, classification in self._session.execute(stmt)
        )

    def list_evidence_transfers(
        self, owner_id: str, evidence_id: str
    ) -> Sequence[EvidenceTransferView]:
        rows = self._session.execute(
            select(TransferredEvidenceRefRow, TransferredEvidenceRefBodyRow)
            .join(
                TransferredEvidenceRefBodyRow,
                TransferredEvidenceRefBodyRow.transfer_id
                == TransferredEvidenceRefRow.id,
            )
            .where(TransferredEvidenceRefRow.owner_id == owner_id)
            .where(TransferredEvidenceRefRow.source_evidence_id == evidence_id)
            .order_by(
                TransferredEvidenceRefRow.created_at, TransferredEvidenceRefRow.id
            )
        ).all()
        return tuple(
            EvidenceTransferView(
                row.id,
                row.goal_id,
                row.learning_state_id,
                row.classification,
                body.rationale,
                row.created_at,
            )
            for row, body in rows
        )

    def get_learning_state_for_topic(
        self, owner_id: str, goal_id: str, topic_stable_id: str
    ) -> LearningState | None:
        pair = self._session.execute(
            select(LearningStateRow, LearningStateBodyRow)
            .join(
                LearningStateBodyRow,
                LearningStateBodyRow.state_id == LearningStateRow.id,
            )
            .where(
                LearningStateRow.owner_id == owner_id,
                LearningStateRow.goal_id == goal_id,
                LearningStateRow.topic_stable_id == topic_stable_id,
            )
        ).one_or_none()
        return _state(*pair) if pair else None

    def add_transferred_evidence(
        self,
        learning_state: TransferLearningStateView,
        transfer_ref: TransferEvidenceRefView,
    ) -> None:
        state_row = LearningStateRow(
            id=learning_state.id,
            owner_id=learning_state.owner_id,
            goal_id=learning_state.goal_id,
            topic_stable_id=learning_state.topic_stable_id,
            graph_version_id=learning_state.graph_version_id,
            classification=learning_state.classification.value,
            origin=learning_state.origin,
            recommended_depth=learning_state.recommended_depth,
            body_hash=hash_payload(learning_state.explanation),
            derivation_version=learning_state.derivation_version,
            input_hash=learning_state.input_hash,
            derived_at=learning_state.derived_at,
        )
        self._session.add(state_row)
        self._session.flush()
        self._session.add(
            LearningStateBodyRow(
                state_id=learning_state.id,
                owner_id=learning_state.owner_id,
                goal_id=learning_state.goal_id,
                explanation=learning_state.explanation,
            )
        )
        ref_row = TransferredEvidenceRefRow(
            id=transfer_ref.id,
            owner_id=transfer_ref.owner_id,
            goal_id=transfer_ref.goal_id,
            learning_state_id=transfer_ref.learning_state_id,
            source_goal_id=transfer_ref.source_goal_id,
            source_evidence_id=transfer_ref.source_evidence_id,
            classification=transfer_ref.classification.value,
            body_hash=hash_payload(transfer_ref.rationale),
            created_at=transfer_ref.created_at,
        )
        self._session.add(ref_row)
        self._session.flush()
        self._session.add(
            TransferredEvidenceRefBodyRow(
                transfer_id=transfer_ref.id,
                owner_id=transfer_ref.owner_id,
                goal_id=transfer_ref.goal_id,
                rationale=transfer_ref.rationale,
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
                body_hash=hash_payload(
                    "The source evidence was tombstoned when its goal was deleted."
                ),
                derivation_version="transfer-tombstone-v1",
                input_hash="tombstoned",
                derived_at=derived_at,
            )
        )
        self._session.execute(
            update(LearningStateBodyRow)
            .where(
                LearningStateBodyRow.owner_id == owner_id,
                LearningStateBodyRow.state_id.in_(state_ids),
            )
            .values(
                explanation="The source evidence was tombstoned when its goal was deleted."
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
        body = self._session.get(RoadmapIdempotencyBodyRow, row.id)
        if body is None:
            return None
        return RoadmapIdempotencyRecord(
            id=row.id,
            owner_id=row.owner_id,
            goal_id=row.goal_id,
            operation=row.operation,
            idempotency_key=row.idempotency_key,
            request_hash=row.request_hash,
            response_json=body.response_json,
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
                response_hash=hash_payload(record.response_json),
                created_at=record.created_at,
            )
        )
        self._session.flush()
        self._session.add(
            RoadmapIdempotencyBodyRow(
                idempotency_id=record.id,
                owner_id=record.owner_id,
                response_json=record.response_json,
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


def _proposal(row: OverlayProposalRow, body: OverlayProposalBodyRow) -> OverlayProposal:
    return OverlayProposal(
        id=row.id,
        owner_id=row.owner_id,
        goal_id=row.goal_id,
        generated_against_graph_version_id=row.generated_against_graph_version_id,
        topic_stable_id=row.topic_stable_id,
        proposal_type=OverlayProposalType(row.proposal_type),
        payload=json.loads(body.payload_json),
        content_hash=row.content_hash,
        state=OverlayProposalState(row.state),
        state_reason=body.state_reason,
        created_at=row.created_at,
        decided_at=row.decided_at,
    )


def _proposal_decision(
    row: OverlayProposalDecisionRow, body: OverlayProposalDecisionBodyRow
) -> OverlayProposalDecision:
    return OverlayProposalDecision(
        id=row.id,
        owner_id=row.owner_id,
        goal_id=row.goal_id,
        proposal_id=row.proposal_id,
        decision=OverlayDecisionType(row.decision),
        reason=body.reason,
        decided_at=row.decided_at,
    )


def _entry(row: OverlayEntryRow, body: OverlayEntryBodyRow) -> OverlayEntry:
    return OverlayEntry(
        row.id,
        row.owner_id,
        row.goal_id,
        row.overlay_id,
        row.graph_version_id,
        row.topic_stable_id,
        OverlayEntryType(row.entry_type),
        json.loads(body.value_json),
        body.reason,
        row.source,
        row.approved_at,
        row.supersedes_entry_id,
        row.content_hash,
    )


def _state(row: LearningStateRow, body: LearningStateBodyRow) -> LearningState:
    return LearningState(
        row.id,
        row.owner_id,
        row.goal_id,
        row.topic_stable_id,
        row.graph_version_id,
        LearningClassification(row.classification),
        row.origin,
        row.recommended_depth,
        body.explanation,
        row.derivation_version,
        row.input_hash,
        row.derived_at,
    )


def _correction(
    row: LearnerCorrectionRow, body: LearnerCorrectionBodyRow
) -> LearnerCorrection:
    return LearnerCorrection(
        row.id,
        row.owner_id,
        row.goal_id,
        row.topic_stable_id,
        CorrectionType(row.correction_type),
        body.value,
        body.reason,
        row.created_at,
        row.supersedes_correction_id,
    )

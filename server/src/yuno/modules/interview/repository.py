"""Owner-scoped SQLAlchemy interview repository."""

from sqlalchemy import update

from yuno.modules.interview.domain import (
    BundleSubject,
    InterviewBundle,
    InterviewBundleItem,
    InterviewIdempotencyRecord,
    InterviewTurnKind,
    PracticeDimensionResult,
    PracticeRun,
    PracticeRunState,
    PracticeTurn,
    PracticeTurnResult,
)
from yuno.modules.interview.models import (
    InterviewBundleItemRow,
    InterviewBundleRow,
    InterviewIdempotencyRow,
    InterviewRunRow,
    InterviewTurnResultRow,
    InterviewTurnRow,
)
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyInterviewRepository(SqlAlchemyRepository):
    def add_run(self, run: PracticeRun) -> PracticeRun:
        values = {
            k: v for k, v in run.__dict__.items() if k not in {"turns", "results"}
        }
        values["state"] = run.state.value
        values["retryable"] = int(run.retryable)
        self._session.add(InterviewRunRow(**values))
        self._session.flush()
        return self.get_run(run.owner_id, run.id)  # type: ignore[return-value]

    def get_run(self, owner_id: str, run_id: str) -> PracticeRun | None:
        row = self._session.scalars(
            owner_scoped_select(InterviewRunRow, owner_id).where(
                InterviewRunRow.id == run_id
            )
        ).one_or_none()
        if row is None:
            return None
        turns = self._session.scalars(
            owner_scoped_select(InterviewTurnRow, owner_id)
            .where(InterviewTurnRow.run_id == run_id)
            .order_by(InterviewTurnRow.turn_number)
        ).all()
        results = self._session.scalars(
            owner_scoped_select(InterviewTurnResultRow, owner_id)
            .where(InterviewTurnResultRow.run_id == run_id)
            .order_by(InterviewTurnResultRow.visible_at, InterviewTurnResultRow.id)
        ).all()
        return PracticeRun(
            row.id,
            row.owner_id,
            row.goal_id,
            row.bundle_id,
            row.bundle_item_id,
            row.mode,
            PracticeRunState(row.state),
            row.question,
            row.hint_text,
            row.rubric_id,
            row.rubric_version,
            row.requested_capability,
            row.active_job_id,
            row.active_answer_turn_id,
            row.failure_reference,
            bool(row.retryable),
            row.created_at,
            row.updated_at,
            tuple(_turn(item) for item in turns),
            tuple(_result(item) for item in results),
        )

    def add_turn(self, turn: PracticeTurn) -> PracticeTurn:
        values = turn.__dict__.copy()
        values["kind"] = turn.kind.value
        self._session.add(InterviewTurnRow(**values))
        self._session.flush()
        return turn

    def add_turn_result(self, result: PracticeTurnResult) -> PracticeTurnResult:
        values = result.__dict__.copy()
        values["facts"] = list(result.facts)
        values["trade_offs"] = list(result.trade_offs)
        values["dimensions"] = [item.__dict__ for item in result.dimensions]
        self._session.add(InterviewTurnResultRow(**values))
        self._session.flush()
        return result

    def update_run(
        self, owner_id: str, run_id: str, changes: dict[str, object]
    ) -> PracticeRun | None:
        values = {
            key: (
                value.value
                if isinstance(value, PracticeRunState)
                else int(value)
                if key == "retryable"
                else value
            )
            for key, value in changes.items()
        }
        result = self._session.execute(
            update(InterviewRunRow)
            .where(InterviewRunRow.owner_id == owner_id, InterviewRunRow.id == run_id)
            .values(**values)
        )
        self._session.flush()
        return self.get_run(owner_id, run_id) if result.rowcount == 1 else None

    def add_bundle(self, bundle: InterviewBundle) -> InterviewBundle:
        row = InterviewBundleRow(
            **{k: v for k, v in bundle.__dict__.items() if k != "items"}
        )
        row.items = [
            InterviewBundleItemRow(
                **{
                    **item.__dict__,
                    "subject": item.subject.value,
                    "is_optional": int(item.is_optional),
                    "included": int(item.included),
                }
            )
            for item in bundle.items
        ]
        self._session.add(row)
        self._session.flush()
        return self.get_bundle(bundle.owner_id, bundle.id)  # type: ignore[return-value]

    def get_bundle(self, owner_id: str, bundle_id: str) -> InterviewBundle | None:
        row = self._session.scalars(
            owner_scoped_select(InterviewBundleRow, owner_id).where(
                InterviewBundleRow.id == bundle_id
            )
        ).one_or_none()
        return _bundle(row) if row and row.status != "archived" else None

    def list_bundles(self, owner_id: str, goal_id: str | None = None):
        query = owner_scoped_select(InterviewBundleRow, owner_id).where(
            InterviewBundleRow.status != "archived"
        )
        if goal_id is not None:
            query = query.where(InterviewBundleRow.goal_id == goal_id)
        rows = self._session.scalars(
            query.order_by(InterviewBundleRow.created_at, InterviewBundleRow.id)
        ).all()
        return tuple(_bundle(row) for row in rows)

    def update_bundle(
        self,
        owner_id: str,
        bundle_id: str,
        expected_version: int,
        changes: dict[str, object],
        item_changes: dict[str, bool],
    ) -> InterviewBundle | None:
        result = self._session.execute(
            update(InterviewBundleRow)
            .where(
                InterviewBundleRow.owner_id == owner_id,
                InterviewBundleRow.id == bundle_id,
                InterviewBundleRow.row_version == expected_version,
            )
            .values(**changes, row_version=expected_version + 1)
        )
        if result.rowcount != 1:
            return None
        for item_id, included in item_changes.items():
            self._session.execute(
                update(InterviewBundleItemRow)
                .where(
                    InterviewBundleItemRow.owner_id == owner_id,
                    InterviewBundleItemRow.bundle_id == bundle_id,
                    InterviewBundleItemRow.id == item_id,
                )
                .values(included=int(included))
            )
        self._session.flush()
        return self.get_bundle(owner_id, bundle_id)

    def delete_bundle(self, owner_id: str, bundle_id: str) -> bool:
        result = self._session.execute(
            update(InterviewBundleRow)
            .where(
                InterviewBundleRow.owner_id == owner_id,
                InterviewBundleRow.id == bundle_id,
                InterviewBundleRow.status != "archived",
            )
            .values(status="archived", row_version=InterviewBundleRow.row_version + 1)
        )
        self._session.flush()
        return result.rowcount == 1

    def get_idempotency(self, owner_id: str, operation: str, key: str):
        row = self._session.scalars(
            owner_scoped_select(InterviewIdempotencyRow, owner_id).where(
                InterviewIdempotencyRow.operation == operation,
                InterviewIdempotencyRow.idempotency_key == key,
            )
        ).one_or_none()
        return (
            InterviewIdempotencyRecord(
                row.id,
                row.owner_id,
                row.operation,
                row.idempotency_key,
                row.request_hash,
                row.response_json,
                row.created_at,
            )
            if row
            else None
        )

    def add_idempotency(self, record: InterviewIdempotencyRecord) -> None:
        self._session.add(InterviewIdempotencyRow(**record.__dict__))
        self._session.flush()


def _bundle(row: InterviewBundleRow) -> InterviewBundle:
    return InterviewBundle(
        row.id,
        row.owner_id,
        row.goal_id,
        row.name,
        row.generic_role,
        row.target_level,
        row.origin,
        row.copy_source_id,
        row.status,
        row.row_version,
        row.created_at,
        row.updated_at,
        tuple(
            InterviewBundleItem(
                item.id,
                item.owner_id,
                item.bundle_id,
                BundleSubject(item.subject),
                item.topic_stable_id,
                item.question,
                item.position,
                bool(item.is_optional),
                bool(item.included),
            )
            for item in row.items
        ),
    )


def _turn(row: InterviewTurnRow) -> PracticeTurn:
    return PracticeTurn(
        row.id,
        row.owner_id,
        row.run_id,
        row.turn_number,
        InterviewTurnKind(row.kind),
        row.body,
        row.answer_turn_id,
        row.evidence_id,
        row.created_at,
    )


def _result(row: InterviewTurnResultRow) -> PracticeTurnResult:
    return PracticeTurnResult(
        row.id,
        row.owner_id,
        row.run_id,
        row.answer_turn_id,
        row.assessment_id,
        row.visible_at,
        tuple(row.facts),
        tuple(row.trade_offs),
        tuple(PracticeDimensionResult(**item) for item in row.dimensions),
        row.feedback,
        row.cross_question_candidate,
    )

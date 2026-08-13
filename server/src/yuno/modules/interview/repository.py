"""Owner-scoped SQLAlchemy interview repository."""

import json

from sqlalchemy import func, select, update

from yuno.modules.data_lifecycle.models import (
    InterviewIdempotencyBodyRow,
    InterviewRunBodyRow,
    InterviewTurnBodyRow,
    InterviewTurnResultBodyRow,
)
from yuno.modules.interview.domain import (
    BundleSubject,
    InterviewBundle,
    InterviewBundleItem,
    InterviewIdempotencyRecord,
    InterviewTurnKind,
    MockRunState,
    PracticeDimensionResult,
    PracticeRun,
    PracticeRunState,
    PracticeTurn,
    PracticeTurnResult,
)
from yuno.modules.interview.models import (
    InterviewBundleBodyRow,
    InterviewBundleItemBodyRow,
    InterviewBundleItemRow,
    InterviewBundleRow,
    InterviewIdempotencyRow,
    InterviewRunRow,
    InterviewTurnResultRow,
    InterviewTurnRow,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyInterviewRepository(SqlAlchemyRepository):
    def count_live_sessions(self, owner_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(InterviewRunBodyRow)
                .where(InterviewRunBodyRow.owner_id == owner_id)
            )
            or 0
        )

    def count_turns(self, owner_id: str, run_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(InterviewTurnBodyRow)
                .join(
                    InterviewTurnRow,
                    InterviewTurnRow.id == InterviewTurnBodyRow.turn_id,
                )
                .where(
                    InterviewTurnBodyRow.owner_id == owner_id,
                    InterviewTurnRow.run_id == run_id,
                )
            )
            or 0
        )

    def session_body_utf8_bytes(self, owner_id: str, run_id: str) -> int:
        run_body = self._session.scalars(
            select(InterviewRunBodyRow).where(
                InterviewRunBodyRow.owner_id == owner_id,
                InterviewRunBodyRow.run_id == run_id,
            )
        ).one_or_none()
        turn_bodies = self._session.scalars(
            select(InterviewTurnBodyRow.body)
            .join(InterviewTurnRow, InterviewTurnRow.id == InterviewTurnBodyRow.turn_id)
            .where(
                InterviewTurnBodyRow.owner_id == owner_id,
                InterviewTurnRow.run_id == run_id,
            )
        ).all()
        result_bodies = self._session.scalars(
            select(InterviewTurnResultBodyRow)
            .join(
                InterviewTurnResultRow,
                InterviewTurnResultRow.id == InterviewTurnResultBodyRow.result_id,
            )
            .where(
                InterviewTurnResultBodyRow.owner_id == owner_id,
                InterviewTurnResultRow.run_id == run_id,
            )
        ).all()
        values: list[str] = list(turn_bodies)
        if run_body is not None:
            values.extend(
                value
                for value in (
                    run_body.question,
                    run_body.hint_text,
                    run_body.draft,
                )
                if value is not None
            )
        for body in result_bodies:
            values.extend(
                value
                for value in (
                    body.feedback,
                    body.cross_question_candidate,
                    body.facts_json,
                    body.trade_offs_json,
                    body.dimensions_json,
                )
                if value is not None
            )
        return sum(len(value.encode("utf-8")) for value in values)

    def add_run(self, run: PracticeRun) -> PracticeRun:
        values = {
            k: v for k, v in run.__dict__.items() if k not in {"turns", "results"}
        }
        for key in ("question", "hint_text", "draft"):
            values.pop(key)
        values["state"] = run.state.value
        values["retryable"] = int(run.retryable)
        values["body_hash"] = hash_payload(
            {
                "question": run.question,
                "hint_text": run.hint_text,
                "draft": run.draft,
            }
        )
        self._session.add(InterviewRunRow(**values))
        self._session.flush()
        self._session.add(
            InterviewRunBodyRow(
                run_id=run.id,
                owner_id=run.owner_id,
                goal_id=run.goal_id,
                question=run.question,
                hint_text=run.hint_text,
                draft=run.draft,
            )
        )
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
        run_body = self._session.get(InterviewRunBodyRow, row.id)
        if run_body is None:
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
        turn_values: list[PracticeTurn] = []
        for item in turns:
            body = self._session.get(InterviewTurnBodyRow, item.id)
            if body is None:
                return None
            turn_values.append(_turn(item, body.body))
        result_values: list[PracticeTurnResult] = []
        for item in results:
            body = self._session.get(InterviewTurnResultBodyRow, item.id)
            if body is None:
                return None
            result_values.append(_result(item, body))
        return PracticeRun(
            row.id,
            row.owner_id,
            row.goal_id,
            row.bundle_id,
            row.bundle_item_id,
            row.mode,
            PracticeRunState(row.state)
            if row.mode == "Practice"
            else MockRunState(row.state),
            run_body.question,
            run_body.hint_text,
            row.rubric_id,
            row.rubric_version,
            row.requested_capability,
            row.active_job_id,
            row.active_answer_turn_id,
            row.failure_reference,
            bool(row.retryable),
            run_body.draft,
            row.final_assessment_id,
            row.created_at,
            row.updated_at,
            tuple(turn_values),
            tuple(result_values),
        )

    def add_turn(self, turn: PracticeTurn) -> PracticeTurn:
        values = turn.__dict__.copy()
        values.pop("body")
        values["kind"] = turn.kind.value
        values["body_hash"] = hash_payload(turn.body)
        self._session.add(InterviewTurnRow(**values))
        self._session.flush()
        self._session.add(
            InterviewTurnBodyRow(
                turn_id=turn.id, owner_id=turn.owner_id, body=turn.body
            )
        )
        self._session.flush()
        return turn

    def add_turn_result(self, result: PracticeTurnResult) -> PracticeTurnResult:
        values = result.__dict__.copy()
        for key in (
            "facts",
            "trade_offs",
            "dimensions",
            "feedback",
            "cross_question_candidate",
        ):
            values.pop(key)
        values["body_hash"] = hash_payload(
            {
                "facts": result.facts,
                "trade_offs": result.trade_offs,
                "dimensions": result.dimensions,
                "feedback": result.feedback,
                "cross_question_candidate": result.cross_question_candidate,
            }
        )
        self._session.add(InterviewTurnResultRow(**values))
        self._session.flush()
        self._session.add(
            InterviewTurnResultBodyRow(
                result_id=result.id,
                owner_id=result.owner_id,
                feedback=result.feedback,
                cross_question_candidate=result.cross_question_candidate,
                facts_json=json.dumps(list(result.facts), separators=(",", ":")),
                trade_offs_json=json.dumps(
                    list(result.trade_offs), separators=(",", ":")
                ),
                dimensions_json=json.dumps(
                    [item.__dict__ for item in result.dimensions], separators=(",", ":")
                ),
            )
        )
        self._session.flush()
        return result

    def update_run(
        self, owner_id: str, run_id: str, changes: dict[str, object]
    ) -> PracticeRun | None:
        body_values = {
            key: changes[key]
            for key in ("question", "hint_text", "draft")
            if key in changes
        }
        if body_values:
            current_body = self._session.get(InterviewRunBodyRow, run_id)
            if current_body is None or current_body.owner_id != owner_id:
                return None
        values = {
            key: (
                value.value
                if isinstance(value, (PracticeRunState, MockRunState))
                else int(value)
                if key == "retryable"
                else value
            )
            for key, value in changes.items()
            if key not in body_values
        }
        if body_values:
            values["body_hash"] = hash_payload(
                {
                    "question": body_values.get("question", current_body.question),
                    "hint_text": body_values.get("hint_text", current_body.hint_text),
                    "draft": body_values.get("draft", current_body.draft),
                }
            )
        result = self._session.execute(
            update(InterviewRunRow)
            .where(InterviewRunRow.owner_id == owner_id, InterviewRunRow.id == run_id)
            .values(**values)
        )
        if body_values:
            self._session.execute(
                update(InterviewRunBodyRow)
                .where(
                    InterviewRunBodyRow.owner_id == owner_id,
                    InterviewRunBodyRow.run_id == run_id,
                )
                .values(**body_values)
            )
        self._session.flush()
        return self.get_run(owner_id, run_id) if result.rowcount == 1 else None

    def add_bundle(self, bundle: InterviewBundle) -> InterviewBundle:
        values = bundle.__dict__.copy()
        values.pop("items")
        bundle_body = {
            key: values.pop(key) for key in ("name", "generic_role", "origin")
        }
        values["body_hash"] = hash_payload(bundle_body)
        row = InterviewBundleRow(**values)
        self._session.add(row)
        self._session.flush()
        self._session.add(
            InterviewBundleBodyRow(
                bundle_id=bundle.id, owner_id=bundle.owner_id, **bundle_body
            )
        )
        for item in bundle.items:
            item_values = item.__dict__.copy()
            question = item_values.pop("question")
            item_values["subject"] = item.subject.value
            item_values["is_optional"] = int(item.is_optional)
            item_values["included"] = int(item.included)
            item_values["body_hash"] = hash_payload(question)
            self._session.add(InterviewBundleItemRow(**item_values))
            self._session.flush()
            self._session.add(
                InterviewBundleItemBodyRow(
                    item_id=item.id, owner_id=item.owner_id, question=question
                )
            )
        self._session.flush()
        return self.get_bundle(bundle.owner_id, bundle.id)  # type: ignore[return-value]

    def get_bundle(self, owner_id: str, bundle_id: str) -> InterviewBundle | None:
        row = self._session.scalars(
            owner_scoped_select(InterviewBundleRow, owner_id).where(
                InterviewBundleRow.id == bundle_id
            )
        ).one_or_none()
        return _bundle(row, self._session) if row and row.status != "archived" else None

    def list_bundles(self, owner_id: str, goal_id: str | None = None):
        query = owner_scoped_select(InterviewBundleRow, owner_id).where(
            InterviewBundleRow.status != "archived"
        )
        if goal_id is not None:
            query = query.where(InterviewBundleRow.goal_id == goal_id)
        rows = self._session.scalars(
            query.order_by(InterviewBundleRow.created_at, InterviewBundleRow.id)
        ).all()
        return tuple(_bundle(row, self._session) for row in rows)

    def update_bundle(
        self,
        owner_id: str,
        bundle_id: str,
        expected_version: int,
        changes: dict[str, object],
        item_changes: dict[str, bool],
    ) -> InterviewBundle | None:
        body_changes = {
            key: changes.pop(key)
            for key in ("name", "generic_role", "origin")
            if key in changes
        }
        if body_changes:
            current = self._session.get(InterviewBundleBodyRow, bundle_id)
            if current is None or current.owner_id != owner_id:
                return None
            changes["body_hash"] = hash_payload(
                {
                    "name": body_changes.get("name", current.name),
                    "generic_role": body_changes.get(
                        "generic_role", current.generic_role
                    ),
                    "origin": body_changes.get("origin", current.origin),
                }
            )
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
        if body_changes:
            self._session.execute(
                update(InterviewBundleBodyRow)
                .where(
                    InterviewBundleBodyRow.owner_id == owner_id,
                    InterviewBundleBodyRow.bundle_id == bundle_id,
                )
                .values(**body_changes)
            )
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
        body = self._session.get(InterviewIdempotencyBodyRow, row.id) if row else None
        return (
            InterviewIdempotencyRecord(
                row.id,
                row.owner_id,
                row.operation,
                row.idempotency_key,
                row.request_hash,
                body.response_json,
                row.created_at,
            )
            if row and body
            else None
        )

    def add_idempotency(self, record: InterviewIdempotencyRecord) -> None:
        values = record.__dict__.copy()
        response_json = values.pop("response_json")
        values["response_hash"] = hash_payload(response_json)
        self._session.add(InterviewIdempotencyRow(**values))
        self._session.flush()
        self._session.add(
            InterviewIdempotencyBodyRow(
                idempotency_id=record.id,
                owner_id=record.owner_id,
                response_json=response_json,
            )
        )
        self._session.flush()


def _bundle(row: InterviewBundleRow, session) -> InterviewBundle:
    body = session.get(InterviewBundleBodyRow, row.id)
    if body is None:
        raise RuntimeError("Interview bundle body is unavailable.")
    return InterviewBundle(
        row.id,
        row.owner_id,
        row.goal_id,
        body.name,
        body.generic_role,
        row.target_level,
        body.origin,
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
                session.get(InterviewBundleItemBodyRow, item.id).question,
                item.position,
                bool(item.is_optional),
                bool(item.included),
            )
            for item in row.items
        ),
    )


def _turn(row: InterviewTurnRow, body: str) -> PracticeTurn:
    return PracticeTurn(
        row.id,
        row.owner_id,
        row.run_id,
        row.turn_number,
        InterviewTurnKind(row.kind),
        body,
        row.answer_turn_id,
        row.evidence_id,
        row.created_at,
    )


def _result(
    row: InterviewTurnResultRow, body: InterviewTurnResultBodyRow
) -> PracticeTurnResult:
    return PracticeTurnResult(
        row.id,
        row.owner_id,
        row.run_id,
        row.answer_turn_id,
        row.assessment_id,
        row.visible_at,
        tuple(json.loads(body.facts_json)),
        tuple(json.loads(body.trade_offs_json)),
        tuple(
            PracticeDimensionResult(**item) for item in json.loads(body.dimensions_json)
        ),
        body.feedback,
        body.cross_question_candidate,
    )

"""Owner-scoped SQLAlchemy notebook/review repository."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from sqlalchemy import update

from yuno.modules.data_lifecycle.models import NotebookReviewIdempotencyBodyRow
from yuno.modules.notebook_review.domain import (
    GoalReviewPreferences,
    NotebookEntry,
    NotebookEntryKind,
    NotebookReviewIdempotencyRecord,
    ReviewAttempt,
    ReviewCadence,
    ReviewConfidence,
    ReviewItem,
    ReviewItemStatus,
    ReviewPromptType,
)
from yuno.modules.notebook_review.models import (
    GoalReviewPreferencesRow,
    NotebookEntryBodyRow,
    NotebookEntryRow,
    NotebookReviewIdempotencyRow,
    ReviewAttemptBodyRow,
    ReviewAttemptRow,
    ReviewItemBodyRow,
    ReviewItemRow,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemyNotebookReviewRepository(SqlAlchemyRepository):
    def add_entry(self, entry: NotebookEntry) -> NotebookEntry:
        values = entry.__dict__.copy()
        markdown = values.pop("markdown")
        values["entry_kind"] = entry.entry_kind.value
        values["body_hash"] = _body_hash(markdown=markdown)
        self._session.add(NotebookEntryRow(**values))
        self._session.flush()
        self._session.add(
            NotebookEntryBodyRow(
                entry_id=entry.id,
                owner_id=entry.owner_id,
                goal_id=entry.goal_id,
                markdown=markdown,
            )
        )
        return entry

    def get_entry(self, owner_id: str, entry_id: str) -> NotebookEntry | None:
        row = self._session.scalars(
            owner_scoped_select(NotebookEntryRow, owner_id).where(
                NotebookEntryRow.id == entry_id
            )
        ).one_or_none()
        return _entry(row) if row else None

    def list_entries(self, owner_id: str, goal_id: str) -> Sequence[NotebookEntry]:
        rows = self._session.scalars(
            owner_scoped_select(NotebookEntryRow, owner_id)
            .where(
                NotebookEntryRow.goal_id == goal_id,
                NotebookEntryRow.tombstoned_at.is_(None),
            )
            .order_by(NotebookEntryRow.updated_at.desc(), NotebookEntryRow.id)
        ).all()
        return tuple(item for row in rows if (item := _entry(row)) is not None)

    def update_entry(
        self,
        owner_id: str,
        entry_id: str,
        expected_version: int,
        changes: dict[str, object],
    ) -> NotebookEntry | None:
        values = {
            key: value.value if isinstance(value, NotebookEntryKind) else value
            for key, value in changes.items()
        }
        markdown = values.pop("markdown", None)
        if markdown is not None:
            values["body_hash"] = _body_hash(markdown=markdown)
        values["row_version"] = expected_version + 1
        result = self._session.execute(
            update(NotebookEntryRow)
            .where(
                NotebookEntryRow.owner_id == owner_id,
                NotebookEntryRow.id == entry_id,
                NotebookEntryRow.row_version == expected_version,
                NotebookEntryRow.tombstoned_at.is_(None),
            )
            .values(**values)
        )
        if result.rowcount != 1:
            return None
        if markdown is not None:
            self._session.execute(
                update(NotebookEntryBodyRow)
                .where(
                    NotebookEntryBodyRow.owner_id == owner_id,
                    NotebookEntryBodyRow.entry_id == entry_id,
                )
                .values(markdown=markdown)
            )
        self._session.flush()
        return self.get_entry(owner_id, entry_id)

    def get_preferences(
        self, owner_id: str, goal_id: str
    ) -> GoalReviewPreferences | None:
        row = self._session.scalars(
            owner_scoped_select(GoalReviewPreferencesRow, owner_id).where(
                GoalReviewPreferencesRow.goal_id == goal_id
            )
        ).one_or_none()
        return _preferences(row) if row else None

    def put_preferences(
        self, preferences: GoalReviewPreferences, expected_version: int
    ) -> GoalReviewPreferences | None:
        values = preferences.__dict__.copy()
        values.update(
            enabled=int(preferences.enabled),
            cadence=preferences.cadence.value,
            retrieval_enabled=int(preferences.retrieval_enabled),
            varied_context_enabled=int(preferences.varied_context_enabled),
        )
        existing = self.get_preferences(preferences.owner_id, preferences.goal_id)
        if existing is None:
            if expected_version != 1:
                return None
            self._session.add(GoalReviewPreferencesRow(**values))
        else:
            result = self._session.execute(
                update(GoalReviewPreferencesRow)
                .where(
                    GoalReviewPreferencesRow.owner_id == preferences.owner_id,
                    GoalReviewPreferencesRow.goal_id == preferences.goal_id,
                    GoalReviewPreferencesRow.row_version == expected_version,
                )
                .values(
                    **{
                        key: value
                        for key, value in values.items()
                        if key not in {"owner_id", "goal_id"}
                    }
                )
            )
            if result.rowcount != 1:
                return None
        self._session.flush()
        return self.get_preferences(preferences.owner_id, preferences.goal_id)

    def add_review_item(self, item: ReviewItem) -> ReviewItem:
        values = item.__dict__.copy()
        body = {key: values.pop(key) for key in ("prompt", "answer", "context")}
        values.update(prompt_type=item.prompt_type.value, status=item.status.value)
        values["body_hash"] = _body_hash(**body)
        self._session.add(ReviewItemRow(**values))
        self._session.flush()
        self._session.add(
            ReviewItemBodyRow(
                review_item_id=item.id,
                owner_id=item.owner_id,
                goal_id=item.goal_id,
                **body,
            )
        )
        return item

    def get_review_item(self, owner_id: str, review_id: str) -> ReviewItem | None:
        row = self._session.scalars(
            owner_scoped_select(ReviewItemRow, owner_id).where(
                ReviewItemRow.id == review_id
            )
        ).one_or_none()
        return _item(row) if row else None

    def list_review_items(self, owner_id: str, goal_id: str) -> Sequence[ReviewItem]:
        rows = self._session.scalars(
            owner_scoped_select(ReviewItemRow, owner_id)
            .where(ReviewItemRow.goal_id == goal_id)
            .order_by(ReviewItemRow.due_at, ReviewItemRow.created_at, ReviewItemRow.id)
        ).all()
        return tuple(item for row in rows if (item := _item(row)) is not None)

    def transition_review_item(
        self,
        owner_id: str,
        review_id: str,
        expected_status: str,
        changes: dict[str, object],
    ) -> ReviewItem | None:
        values = {
            key: value.value if isinstance(value, ReviewItemStatus) else value
            for key, value in changes.items()
        }
        body_values = {
            key: values.pop(key)
            for key in ("prompt", "answer", "context")
            if key in values
        }
        if body_values:
            current = self._session.get(ReviewItemBodyRow, review_id)
            if current is None or current.owner_id != owner_id:
                return None
            merged = {
                "prompt": current.prompt,
                "answer": current.answer,
                "context": current.context,
                **body_values,
            }
            values["body_hash"] = _body_hash(**merged)
        result = self._session.execute(
            update(ReviewItemRow)
            .where(
                ReviewItemRow.owner_id == owner_id,
                ReviewItemRow.id == review_id,
                ReviewItemRow.status == expected_status,
            )
            .values(**values, row_version=ReviewItemRow.row_version + 1)
        )
        if result.rowcount != 1:
            return None
        if body_values:
            self._session.execute(
                update(ReviewItemBodyRow)
                .where(
                    ReviewItemBodyRow.owner_id == owner_id,
                    ReviewItemBodyRow.review_item_id == review_id,
                )
                .values(**body_values)
            )
        self._session.flush()
        return self.get_review_item(owner_id, review_id)

    def add_attempt(self, attempt: ReviewAttempt) -> ReviewAttempt:
        values = attempt.__dict__.copy()
        body = {
            key: values.pop(key)
            for key in (
                "response",
                "feedback",
                "correction",
                "context_variation",
                "context_result",
            )
        }
        values["confidence"] = attempt.confidence.value if attempt.confidence else None
        values["body_hash"] = _body_hash(**body)
        self._session.add(ReviewAttemptRow(**values))
        self._session.flush()
        self._session.add(
            ReviewAttemptBodyRow(
                attempt_id=attempt.id,
                owner_id=attempt.owner_id,
                goal_id=attempt.goal_id,
                **body,
            )
        )
        return attempt

    def list_attempts(self, owner_id: str, review_id: str) -> Sequence[ReviewAttempt]:
        rows = self._session.scalars(
            owner_scoped_select(ReviewAttemptRow, owner_id)
            .where(ReviewAttemptRow.review_item_id == review_id)
            .order_by(ReviewAttemptRow.created_at, ReviewAttemptRow.id)
        ).all()
        return tuple(item for row in rows if (item := _attempt(row)) is not None)

    def disable_active_review_items(
        self, owner_id: str, goal_id: str, updated_at: str
    ) -> None:
        self._session.execute(
            update(ReviewItemRow)
            .where(
                ReviewItemRow.owner_id == owner_id,
                ReviewItemRow.goal_id == goal_id,
                ReviewItemRow.status.in_(
                    (ReviewItemStatus.READY.value, ReviewItemStatus.DUE.value)
                ),
            )
            .values(
                status=ReviewItemStatus.DISABLED.value,
                updated_at=updated_at,
                row_version=ReviewItemRow.row_version + 1,
            )
        )
        self._session.flush()

    def get_idempotency(
        self, owner_id: str, operation: str, key: str
    ) -> NotebookReviewIdempotencyRecord | None:
        row = self._session.scalars(
            owner_scoped_select(NotebookReviewIdempotencyRow, owner_id).where(
                NotebookReviewIdempotencyRow.operation == operation,
                NotebookReviewIdempotencyRow.idempotency_key == key,
            )
        ).one_or_none()
        body = (
            self._session.get(NotebookReviewIdempotencyBodyRow, row.id) if row else None
        )
        return (
            NotebookReviewIdempotencyRecord(
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

    def add_idempotency(self, record: NotebookReviewIdempotencyRecord) -> None:
        values = record.__dict__.copy()
        response_json = values.pop("response_json")
        values["response_hash"] = hash_payload(response_json)
        self._session.add(NotebookReviewIdempotencyRow(**values))
        self._session.flush()
        self._session.add(
            NotebookReviewIdempotencyBodyRow(
                idempotency_id=record.id,
                owner_id=record.owner_id,
                response_json=response_json,
            )
        )
        self._session.flush()


def _entry(row: NotebookEntryRow) -> NotebookEntry | None:
    body = row.body
    if body is None:
        return None
    return NotebookEntry(
        row.id,
        row.owner_id,
        row.goal_id,
        row.topic_stable_id,
        row.evidence_id,
        row.source_id,
        NotebookEntryKind(row.entry_kind),
        body.markdown,
        row.row_version,
        row.created_at,
        row.updated_at,
        row.tombstoned_at,
    )


def _preferences(row: GoalReviewPreferencesRow) -> GoalReviewPreferences:
    return GoalReviewPreferences(
        row.owner_id,
        row.goal_id,
        bool(row.enabled),
        row.duration_minutes,
        ReviewCadence(row.cadence),
        bool(row.retrieval_enabled),
        bool(row.varied_context_enabled),
        row.scheduling_version,
        row.row_version,
        row.updated_at,
    )


def _item(row: ReviewItemRow) -> ReviewItem | None:
    body = row.body
    if body is None:
        return None
    return ReviewItem(
        row.id,
        row.owner_id,
        row.goal_id,
        row.topic_stable_id,
        row.prompt_ref,
        ReviewPromptType(row.prompt_type),
        body.prompt,
        body.answer,
        ReviewItemStatus(row.status),
        row.due_at,
        row.interval_label,
        body.context,
        row.scheduling_version,
        row.failure_reference,
        row.row_version,
        row.created_at,
        row.updated_at,
    )


def _attempt(row: ReviewAttemptRow) -> ReviewAttempt | None:
    body = row.body
    if body is None:
        return None
    return ReviewAttempt(
        row.id,
        row.owner_id,
        row.goal_id,
        row.review_item_id,
        body.response,
        ReviewConfidence(row.confidence) if row.confidence else None,
        body.feedback,
        body.correction,
        row.next_interval_label,
        body.context_variation,
        body.context_result,
        row.scheduling_version,
        row.created_at,
    )


def _body_hash(**values: object) -> str:
    encoded = json.dumps(
        values, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

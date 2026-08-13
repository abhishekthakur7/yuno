from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text, update

from yuno.modules.settings_data.domain import (
    DeleteOperation,
    ExportOperation,
    OwnerSettings,
    ProgressDisplay,
)
from yuno.modules.settings_data.models import (
    DeleteOperationRow,
    ExportOperationRow,
    OwnerSettingsRow,
)
from yuno.shared.infrastructure.repository import (
    SqlAlchemyRepository,
    owner_scoped_select,
)


class SqlAlchemySettingsRepository(SqlAlchemyRepository):
    def get(self, owner_id: str) -> OwnerSettings | None:
        row = self._session.scalars(
            owner_scoped_select(OwnerSettingsRow, owner_id)
        ).one_or_none()
        return _settings(row) if row is not None else None

    def create(self, settings: OwnerSettings) -> OwnerSettings:
        self._session.add(
            OwnerSettingsRow(
                owner_id=settings.owner_id,
                progress_display=settings.progress_display.value,
                accessibility_json=json.dumps(
                    settings.accessibility, sort_keys=True, separators=(",", ":")
                ),
                provider_selection=settings.provider_selection,
                row_version=settings.row_version,
                updated_at=settings.updated_at,
            )
        )
        self._session.flush()
        created = self.get(settings.owner_id)
        assert created is not None
        return created

    def update(
        self,
        owner_id: str,
        expected_version: int,
        progress_display: ProgressDisplay,
        accessibility: dict[str, Any],
        provider_selection: str | None,
        *,
        updated_at: str,
    ) -> OwnerSettings | None:
        result = self._session.execute(
            update(OwnerSettingsRow)
            .where(
                OwnerSettingsRow.owner_id == owner_id,
                OwnerSettingsRow.row_version == expected_version,
            )
            .values(
                progress_display=progress_display.value,
                accessibility_json=json.dumps(
                    accessibility, sort_keys=True, separators=(",", ":")
                ),
                provider_selection=provider_selection,
                row_version=expected_version + 1,
                updated_at=updated_at,
            )
        )
        if result.rowcount != 1:
            return None
        self._session.flush()
        return self.get(owner_id)

    def add_export(self, operation: ExportOperation) -> None:
        self._session.add(ExportOperationRow(**operation.__dict__))
        self._session.flush()

    def get_export(self, owner_id: str, operation_id: str) -> ExportOperation | None:
        row = self._session.scalars(
            owner_scoped_select(ExportOperationRow, owner_id).where(
                ExportOperationRow.id == operation_id
            )
        ).one_or_none()
        return (
            ExportOperation(
                **{
                    column: getattr(row, column)
                    for column in ExportOperation.__dataclass_fields__
                }
            )
            if row
            else None
        )

    def complete_export(
        self, owner_id: str, operation_id: str, package_json: str, updated_at: str
    ) -> None:
        self._session.execute(
            update(ExportOperationRow)
            .where(
                ExportOperationRow.owner_id == owner_id,
                ExportOperationRow.id == operation_id,
            )
            .values(
                status="complete",
                package_json=package_json,
                result_ref=f"ExportOperation:{operation_id}",
                updated_at=updated_at,
            )
        )

    def fail_export(
        self, owner_id: str, operation_id: str, diagnostic: str, updated_at: str
    ) -> None:
        self._session.execute(
            update(ExportOperationRow)
            .where(
                ExportOperationRow.owner_id == owner_id,
                ExportOperationRow.id == operation_id,
                ExportOperationRow.status != "complete",
            )
            .values(
                status="failed", failure_reference=diagnostic, updated_at=updated_at
            )
        )

    def set_export_status(
        self, owner_id: str, operation_id: str, status: str, updated_at: str
    ) -> None:
        self._session.execute(
            update(ExportOperationRow)
            .where(
                ExportOperationRow.owner_id == owner_id,
                ExportOperationRow.id == operation_id,
                ExportOperationRow.status != "complete",
            )
            .values(status=status, failure_reference=None, updated_at=updated_at)
        )

    def export_package(
        self, owner_id: str, goal_id: str | None, format_version: str
    ) -> str:
        goal_clause = "AND e.goal_id=:goal_id" if goal_id else ""
        evidence = self._session.execute(
            text(f"""
            SELECT e.id,e.goal_id,e.topic_stable_id,e.evidence_type,e.capability,
              e.payload_hash,e.summary,e.origin,e.created_at,p.content_version,
              CASE WHEN t.evidence_id IS NULL THEN 'available' ELSE 'unavailable' END availability,
              CASE WHEN t.evidence_id IS NULL THEN p.content ELSE NULL END content
            FROM evidence e LEFT JOIN evidence_tombstones t ON t.evidence_id=e.id AND t.owner_id=e.owner_id
              LEFT JOIN evidence_payloads p ON p.evidence_id=e.id AND p.owner_id=e.owner_id
            WHERE e.owner_id=:owner_id {goal_clause} ORDER BY e.goal_id,e.created_at,e.id
        """),
            {"owner_id": owner_id, "goal_id": goal_id},
        ).mappings()

        def owned_rows(
            table: str, *, goal_column: str | None = "goal_id"
        ) -> list[dict[str, Any]]:
            scoped = f" AND {goal_column}=:goal_id" if goal_id and goal_column else ""
            return [
                dict(row)
                for row in self._session.execute(
                    text(
                        f"SELECT * FROM {table} WHERE owner_id=:owner_id{scoped} ORDER BY rowid"
                    ),
                    {"owner_id": owner_id, "goal_id": goal_id},
                ).mappings()
            ]

        package = {
            "product": "Yuno",
            "format_version": format_version,
            "goal_id": goal_id,
            "profile": owned_rows("learner_profiles", goal_column=None),
            "goals": owned_rows("goal_workspaces", goal_column="id"),
            "graph_pins": [
                {"goal_id": row["id"], "graph_version_id": row["graph_version_id"]}
                for row in owned_rows("goal_workspaces", goal_column="id")
            ],
            "overlays": {
                "personal": owned_rows("personal_overlays"),
                "entries": owned_rows("overlay_entries"),
                "proposals": owned_rows("overlay_proposals"),
            },
            "evidence": [dict(row) for row in evidence],
            "notebook": owned_rows("notebook_entries"),
            "review": {
                "preferences": owned_rows("goal_review_preferences"),
                "items": owned_rows("review_items"),
                "attempts": owned_rows("review_attempts"),
            },
            "diagnostics": {
                "sessions": [
                    dict(row)
                    for row in self._session.execute(
                        text(
                            "SELECT id,captured_graph_version_id,question_set_version,state,confirmed_goal_id,row_version,created_at,updated_at,CASE WHEN untrusted_seed_text IS NULL THEN 'not-present' ELSE 'unavailable' END seed_content_availability FROM diagnostic_sessions WHERE owner_id=:owner_id AND (:goal_id IS NULL OR confirmed_goal_id=:goal_id) ORDER BY created_at,id"
                        ),
                        {"owner_id": owner_id, "goal_id": goal_id},
                    ).mappings()
                ]
            },
            "imports": {
                "records": [
                    dict(row)
                    for row in self._session.execute(
                        text(
                            "SELECT id,goal_id,type,original_hash,parser_version,status,failure_code,failure_reference,row_version,created_at,updated_at,'unavailable' original_content_availability,'raw-original-excluded' original_content_reason FROM import_records WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY created_at,id"
                        ),
                        {"owner_id": owner_id, "goal_id": goal_id},
                    ).mappings()
                ],
                "statements": {
                    "availability": "unavailable",
                    "reason": "unreviewed-originals-excluded",
                },
            },
            "generated_artifacts": [
                dict(row)
                for row in self._session.execute(
                    text(
                        "SELECT id,goal_id,graph_version_id,topic_stable_id,layer,artifact_type,state,body_hash,row_version,created_at,updated_at,CASE WHEN body_ref IS NULL THEN 'unavailable' ELSE 'available-by-reference' END content_availability FROM generated_artifacts WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY created_at,id"
                    ),
                    {"owner_id": owner_id, "goal_id": goal_id},
                ).mappings()
            ],
            "artifact_provenance": owned_rows("artifact_provenance_snapshots"),
            "provenance": {
                "sources": owned_rows("sources", goal_column=None),
                "snapshots": owned_rows("source_snapshots", goal_column=None),
                "claims": owned_rows("claims"),
                "citations": owned_rows("citations"),
            },
            "interview_transcripts": {
                "availability": "unavailable",
                "reason": "policy-unconfigured",
            },
        }
        return json.dumps(
            package,
            sort_keys=True,
            separators=(",", ":"),
        )

    def add_delete(self, operation: DeleteOperation) -> None:
        self._session.add(DeleteOperationRow(**operation.__dict__))
        self._session.flush()

    def get_delete(self, owner_id: str, operation_id: str) -> DeleteOperation | None:
        row = self._session.scalars(
            owner_scoped_select(DeleteOperationRow, owner_id).where(
                DeleteOperationRow.id == operation_id
            )
        ).one_or_none()
        return (
            DeleteOperation(
                **{
                    column: getattr(row, column)
                    for column in DeleteOperation.__dataclass_fields__
                }
            )
            if row
            else None
        )

    def queue_delete(
        self, owner_id: str, operation_id: str, job_id: str, updated_at: str
    ) -> None:
        self._session.execute(
            update(DeleteOperationRow)
            .where(
                DeleteOperationRow.owner_id == owner_id,
                DeleteOperationRow.id == operation_id,
                DeleteOperationRow.status == "preflight",
            )
            .values(
                status="queued",
                job_id=job_id,
                confirmed_at=updated_at,
                updated_at=updated_at,
            )
        )

    def complete_delete(
        self, owner_id: str, operation_id: str, updated_at: str
    ) -> None:
        self._session.execute(
            update(DeleteOperationRow)
            .where(
                DeleteOperationRow.owner_id == owner_id,
                DeleteOperationRow.id == operation_id,
            )
            .values(
                status="complete",
                result_ref=f"DeleteOperation:{operation_id}",
                updated_at=updated_at,
            )
        )

    def fail_delete(
        self, owner_id: str, operation_id: str, diagnostic: str, updated_at: str
    ) -> None:
        self._session.execute(
            update(DeleteOperationRow)
            .where(
                DeleteOperationRow.owner_id == owner_id,
                DeleteOperationRow.id == operation_id,
                DeleteOperationRow.status != "complete",
            )
            .values(
                status="failed", failure_reference=diagnostic, updated_at=updated_at
            )
        )

    def set_delete_status(
        self, owner_id: str, operation_id: str, status: str, updated_at: str
    ) -> None:
        self._session.execute(
            update(DeleteOperationRow)
            .where(
                DeleteOperationRow.owner_id == owner_id,
                DeleteOperationRow.id == operation_id,
                DeleteOperationRow.status != "complete",
            )
            .values(status=status, failure_reference=None, updated_at=updated_at)
        )


def _settings(row: OwnerSettingsRow) -> OwnerSettings:
    return OwnerSettings(
        owner_id=row.owner_id,
        progress_display=ProgressDisplay(row.progress_display),
        accessibility=json.loads(row.accessibility_json),
        provider_selection=row.provider_selection,
        row_version=row.row_version,
        updated_at=row.updated_at,
    )

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from yuno.modules.data_lifecycle.models import ExportPackageBodyRow
from yuno.modules.settings_data.domain import (
    BuiltExportPackage,
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

    def publish_export(self, package: BuiltExportPackage) -> None:
        self._session.execute(
            sqlite_insert(ExportPackageBodyRow)
            .values(
                operation_id=package.operation_id,
                owner_id=package.owner_id,
                package_json=package.document,
            )
            .on_conflict_do_update(
                index_elements=[ExportPackageBodyRow.operation_id],
                set_={"package_json": package.document},
            )
        )
        self._session.execute(
            update(ExportOperationRow)
            .where(
                ExportOperationRow.owner_id == package.owner_id,
                ExportOperationRow.id == package.operation_id,
            )
            .values(
                status="complete",
                filename=package.filename,
                package_hash=package.package_hash,
                result_ref=f"ExportOperation:{package.operation_id}",
                failure_reference=None,
                completed_at=package.completed_at,
                package_expires_at=package.package_expires_at,
                metadata_expires_at=package.metadata_expires_at,
                updated_at=package.completed_at,
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

    def read_export_data(self, owner_id: str, goal_id: str | None) -> dict[str, object]:
        params = {"owner_id": owner_id, "goal_id": goal_id}

        def rows(statement: str) -> list[dict[str, Any]]:
            return [
                dict(row)
                for row in self._session.execute(text(statement), params).mappings()
            ]

        profile = rows(
            "SELECT b.experience,b.strengths,b.weaknesses,p.current_goal_id,p.profile_revision,p.updated_at,"
            "CASE WHEN b.owner_id IS NULL THEN 'unavailable' ELSE 'available' END availability,"
            "CASE WHEN b.owner_id IS NULL THEN 'source-missing' ELSE NULL END reason "
            "FROM learner_profiles p LEFT JOIN learner_profile_bodies b ON b.owner_id=p.owner_id WHERE p.owner_id=:owner_id ORDER BY p.owner_id"
        )
        goals = rows(
            "SELECT g.id,b.name,g.path,b.subject,b.role,g.target_level,g.target_capability,g.graph_version_id,g.status,b.resume_position,g.last_accessed_at,g.row_version,g.created_at,g.updated_at,"
            "CASE WHEN b.goal_id IS NULL THEN 'unavailable' ELSE 'available' END availability,"
            "CASE WHEN b.goal_id IS NOT NULL THEN NULL WHEN g.status='tombstoned' THEN 'tombstoned' ELSE 'source-missing' END reason "
            "FROM goal_workspaces g LEFT JOIN goal_workspace_bodies b ON b.goal_id=g.id AND b.owner_id=g.owner_id WHERE g.owner_id=:owner_id AND (:goal_id IS NULL OR g.id=:goal_id) ORDER BY g.created_at,g.id"
        )
        personal_overlays = rows(
            "SELECT id,goal_id,base_graph_version_id,state,row_version,created_at FROM personal_overlays "
            "WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY created_at,id"
        )
        overlay_entries = rows(
            "SELECT e.id,e.goal_id,e.overlay_id,e.graph_version_id,e.topic_stable_id,e.entry_type,b.value_json,b.reason AS body_reason,e.source,e.approved_at,e.supersedes_entry_id,e.content_hash,"
            "CASE WHEN b.entry_id IS NULL THEN 'unavailable' ELSE 'available' END availability,"
            "CASE WHEN b.entry_id IS NULL THEN 'source-missing' ELSE NULL END reason "
            "FROM overlay_entries e LEFT JOIN overlay_entry_bodies b ON b.entry_id=e.id AND b.owner_id=e.owner_id WHERE e.owner_id=:owner_id AND (:goal_id IS NULL OR e.goal_id=:goal_id) ORDER BY e.approved_at,e.id"
        )
        overlay_proposals = rows(
            "SELECT p.id,p.goal_id,p.generated_against_graph_version_id,p.topic_stable_id,p.proposal_type,b.payload_json,p.content_hash,p.state,b.state_reason,p.created_at,p.decided_at,"
            "CASE WHEN b.proposal_id IS NULL THEN 'unavailable' ELSE 'available' END availability,"
            "CASE WHEN b.proposal_id IS NULL THEN 'source-missing' ELSE NULL END reason "
            "FROM overlay_proposals p LEFT JOIN overlay_proposal_bodies b ON b.proposal_id=p.id AND b.owner_id=p.owner_id WHERE p.owner_id=:owner_id AND (:goal_id IS NULL OR p.goal_id=:goal_id) ORDER BY p.created_at,p.id"
        )
        _decode_json_fields(overlay_entries, "value_json")
        _decode_json_fields(overlay_proposals, "payload_json")
        evidence = rows(
            "SELECT e.id,e.goal_id,e.topic_stable_id,e.evidence_type,e.capability,e.payload_hash,e.summary_hash,s.summary,e.origin,e.created_at,p.content_version,"
            "CASE WHEN t.evidence_id IS NOT NULL THEN 'unavailable' WHEN p.evidence_id IS NULL OR s.evidence_id IS NULL THEN 'unavailable' ELSE 'available' END availability,"
            "CASE WHEN t.evidence_id IS NOT NULL THEN 'tombstoned' WHEN p.evidence_id IS NULL OR s.evidence_id IS NULL THEN 'source-missing' ELSE NULL END reason,"
            "CASE WHEN t.evidence_id IS NULL THEN p.content ELSE NULL END content "
            "FROM evidence e LEFT JOIN evidence_tombstones t ON t.evidence_id=e.id AND t.owner_id=e.owner_id "
            "LEFT JOIN evidence_summary_bodies s ON s.evidence_id=e.id AND s.owner_id=e.owner_id "
            "LEFT JOIN evidence_payloads p ON p.evidence_id=e.id AND p.owner_id=e.owner_id "
            "WHERE e.owner_id=:owner_id AND (:goal_id IS NULL OR e.goal_id=:goal_id) ORDER BY e.goal_id,e.created_at,e.id"
        )
        notebook = rows(
            "SELECT n.id,n.goal_id,n.topic_stable_id,n.evidence_id,n.source_id,n.entry_kind,n.body_hash,n.row_version,n.created_at,n.updated_at,n.tombstoned_at,"
            "CASE WHEN n.tombstoned_at IS NOT NULL OR b.entry_id IS NULL THEN 'unavailable' ELSE 'available' END availability,"
            "CASE WHEN n.tombstoned_at IS NOT NULL THEN 'tombstoned' WHEN b.entry_id IS NULL THEN 'source-missing' ELSE NULL END reason,"
            "CASE WHEN n.tombstoned_at IS NULL THEN b.markdown ELSE NULL END content "
            "FROM notebook_entries n LEFT JOIN notebook_entry_bodies b ON b.entry_id=n.id AND b.owner_id=n.owner_id WHERE n.owner_id=:owner_id AND (:goal_id IS NULL OR n.goal_id=:goal_id) ORDER BY n.created_at,n.id"
        )
        review_preferences = rows(
            "SELECT goal_id,enabled,duration_minutes,cadence,retrieval_enabled,varied_context_enabled,scheduling_version,row_version,updated_at "
            "FROM goal_review_preferences WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY goal_id"
        )
        review_items = rows(
            "SELECT i.id,i.goal_id,i.topic_stable_id,i.prompt_ref,i.prompt_type,b.prompt,b.answer,i.status,i.due_at,i.interval_label,b.context,i.scheduling_version,i.failure_reference,i.body_hash,i.row_version,i.created_at,i.updated_at,"
            "CASE WHEN b.review_item_id IS NULL THEN 'unavailable' ELSE 'available' END availability,CASE WHEN b.review_item_id IS NULL THEN 'source-missing' ELSE NULL END reason "
            "FROM review_items i LEFT JOIN review_item_bodies b ON b.review_item_id=i.id AND b.owner_id=i.owner_id WHERE i.owner_id=:owner_id AND (:goal_id IS NULL OR i.goal_id=:goal_id) ORDER BY i.created_at,i.id"
        )
        review_attempts = rows(
            "SELECT a.id,a.goal_id,a.review_item_id,b.response,a.confidence,b.feedback,b.correction,a.next_interval_label,b.context_variation,b.context_result,a.scheduling_version,a.body_hash,a.created_at,"
            "CASE WHEN b.attempt_id IS NULL THEN 'unavailable' ELSE 'available' END availability,CASE WHEN b.attempt_id IS NULL THEN 'source-missing' ELSE NULL END reason "
            "FROM review_attempts a LEFT JOIN review_attempt_bodies b ON b.attempt_id=a.id AND b.owner_id=a.owner_id WHERE a.owner_id=:owner_id AND (:goal_id IS NULL OR a.goal_id=:goal_id) ORDER BY a.created_at,a.id"
        )
        diagnostics = rows(
            "SELECT id,captured_graph_version_id,question_set_version,setup_inputs_hash,untrusted_seed_kind,untrusted_seed_hash,seed_skipped,diagnostic_skipped,state,started_at,paused_at,expires_at,failure_code,failure_reference,confirmed_goal_id,row_version,created_at,updated_at,"
            "'unavailable' availability,'policy-excluded' reason FROM diagnostic_sessions "
            "WHERE owner_id=:owner_id AND (:goal_id IS NULL OR confirmed_goal_id=:goal_id) ORDER BY created_at,id"
        )
        import_records = rows(
            "SELECT id,goal_id,type,original_hash,parser_version,status,failure_code,failure_reference,row_version,created_at,updated_at,"
            "'unavailable' availability,'raw-original-excluded' reason FROM import_records "
            "WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY created_at,id"
        )
        import_statements = rows(
            "SELECT s.id,s.import_id,s.sequence,s.parser_version,s.original_hash,s.normalized_hash,s.confidence,s.duplicate_of_statement_id,s.trust_state,s.mapping_state,s.corrected_hash,s.row_version,s.created_at,s.updated_at,"
            "CASE WHEN b.statement_id IS NULL THEN 'unavailable' ELSE 'available' END availability,"
            "CASE WHEN b.statement_id IS NULL THEN 'source-missing' ELSE NULL END reason,"
            "b.normalized_text,b.corrected_text,'unavailable' original_availability,'raw-original-excluded' original_reason "
            "FROM import_statements s JOIN import_records r ON r.id=s.import_id AND r.owner_id=s.owner_id "
            "LEFT JOIN import_statement_bodies b ON b.statement_id=s.id AND b.owner_id=s.owner_id "
            "WHERE s.owner_id=:owner_id AND (:goal_id IS NULL OR r.goal_id=:goal_id) ORDER BY s.import_id,s.sequence,s.id"
        )
        import_decisions = rows(
            "SELECT d.id,d.statement_id,d.decision_type,d.value_hash,d.decided_at,"
            "CASE WHEN b.decision_id IS NULL THEN 'unavailable' ELSE 'available' END availability,"
            "CASE WHEN b.decision_id IS NULL THEN 'source-missing' ELSE NULL END reason,b.value "
            "FROM import_statement_decisions d JOIN import_statements s ON s.id=d.statement_id AND s.owner_id=d.owner_id "
            "JOIN import_records r ON r.id=s.import_id AND r.owner_id=s.owner_id "
            "LEFT JOIN import_statement_decision_bodies b ON b.decision_id=d.id AND b.owner_id=d.owner_id "
            "WHERE d.owner_id=:owner_id AND (:goal_id IS NULL OR r.goal_id=:goal_id) ORDER BY d.decided_at,d.id"
        )
        import_mappings = rows(
            "SELECT id,goal_id,statement_id,topic_stable_id,graph_version_id,decision,accepted_at,revoked_at FROM import_statement_mappings "
            "WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY accepted_at,id"
        )
        generated_artifacts = rows(
            "SELECT a.id,a.goal_id,a.graph_version_id,a.topic_stable_id,a.layer,a.artifact_type,a.imports_hash,a.prompt_template_version,a.cache_key_hash,a.state,a.body_hash,a.current_snapshot_id,a.producing_job_id,a.last_attempt_id,a.last_job_id,a.last_attempt_status,a.failure_reference,a.retryable,a.row_version,a.created_at,a.updated_at,a.generated_at,"
            "CASE WHEN b.body_ref LIKE 'inline:%' THEN 'available' ELSE 'unavailable' END availability,"
            "CASE WHEN b.body_ref LIKE 'inline:%' THEN NULL ELSE 'source-missing' END reason,"
            "CASE WHEN b.body_ref LIKE 'inline:%' THEN substr(b.body_ref,8) ELSE NULL END content "
            "FROM generated_artifacts a LEFT JOIN generated_artifact_bodies b ON b.artifact_id=a.id AND b.owner_id=a.owner_id "
            "WHERE a.owner_id=:owner_id AND (:goal_id IS NULL OR a.goal_id=:goal_id) ORDER BY a.created_at,a.id"
        )
        provenance_snapshots = rows(
            "SELECT id,goal_id,artifact_id,attempt_id,evidence_state_hash,profile_hash,provider,model,generated_at,schema_version,contract_version,prompt_template_version,snapshot_hash "
            "FROM artifact_provenance_snapshots WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY generated_at,id"
        )
        provenance_refs = rows(
            "SELECT id,goal_id,artifact_id,snapshot_id,ref_kind,reference_id FROM artifact_provenance_refs "
            "WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY snapshot_id,ref_kind,reference_id,id"
        )
        sources = rows(
            "SELECT s.id,s.origin,s.source_type,b.title,b.publisher,b.canonical_url,s.license_status,s.availability_status,s.body_hash,s.created_at,s.updated_at,CASE WHEN b.source_id IS NULL THEN 'unavailable' ELSE 'available' END availability,CASE WHEN b.source_id IS NULL THEN 'source-missing' ELSE NULL END reason FROM sources s LEFT JOIN source_bodies b ON b.source_id=s.id AND b.owner_id=s.owner_id "
            "WHERE s.owner_id=:owner_id AND (:goal_id IS NULL OR EXISTS (SELECT 1 FROM citations c WHERE c.owner_id=s.owner_id AND c.source_id=s.id AND c.goal_id=:goal_id) OR EXISTS (SELECT 1 FROM notebook_entries n WHERE n.owner_id=s.owner_id AND n.source_id=s.id AND n.goal_id=:goal_id)) ORDER BY s.created_at,s.id"
        )
        source_snapshots = rows(
            "SELECT ss.id,ss.source_id,ss.retrieved_at,ss.content_hash,ss.status,b.version_label,"
            "'unavailable' availability,'policy-excluded' reason FROM source_snapshots ss "
            "LEFT JOIN source_snapshot_bodies b ON b.snapshot_id=ss.id AND b.owner_id=ss.owner_id "
            "WHERE ss.owner_id=:owner_id AND (:goal_id IS NULL OR EXISTS (SELECT 1 FROM citations c WHERE c.owner_id=ss.owner_id AND c.source_snapshot_id=ss.id AND c.goal_id=:goal_id)) ORDER BY ss.retrieved_at,ss.id"
        )
        claims = rows(
            "SELECT c.id,c.goal_id,c.content_revision_id,c.generated_artifact_id,c.snapshot_id,b.claim_text,c.claim_hash,c.claim_type,c.sensitive,c.status,CASE WHEN b.claim_id IS NULL THEN 'unavailable' ELSE 'available' END availability,CASE WHEN b.claim_id IS NULL THEN 'source-missing' ELSE NULL END reason FROM claims c LEFT JOIN claim_bodies b ON b.claim_id=c.id AND b.owner_id=c.owner_id "
            "WHERE c.owner_id=:owner_id AND (:goal_id IS NULL OR c.goal_id=:goal_id) ORDER BY c.id"
        )
        citations = rows(
            "SELECT c.id,c.goal_id,c.claim_id,c.source_id,c.source_snapshot_id,b.locator,c.support_kind,b.note,c.body_hash,CASE WHEN b.citation_id IS NULL THEN 'unavailable' ELSE 'available' END availability,CASE WHEN b.citation_id IS NULL THEN 'source-missing' ELSE NULL END reason FROM citations c LEFT JOIN citation_bodies b ON b.citation_id=c.id AND b.owner_id=c.owner_id "
            "WHERE c.owner_id=:owner_id AND (:goal_id IS NULL OR c.goal_id=:goal_id) ORDER BY c.id"
        )
        interview_runs = rows(
            "SELECT id,goal_id,bundle_id,bundle_item_id,mode,state,rubric_id,rubric_version,requested_capability,active_job_id,active_answer_turn_id,failure_reference,retryable,body_hash,final_assessment_id,created_at,updated_at,"
            "'unavailable' availability,'policy-excluded' reason FROM interview_runs "
            "WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY created_at,id"
        )
        interview_turns = rows(
            "SELECT t.id,t.run_id,t.turn_number,t.kind,t.body_hash,t.answer_turn_id,t.evidence_id,t.created_at,'unavailable' availability,'policy-excluded' reason "
            "FROM interview_turns t JOIN interview_runs r ON r.id=t.run_id AND r.owner_id=t.owner_id "
            "WHERE t.owner_id=:owner_id AND (:goal_id IS NULL OR r.goal_id=:goal_id) ORDER BY t.run_id,t.turn_number,t.id"
        )
        interview_results = rows(
            "SELECT tr.id,tr.run_id,tr.answer_turn_id,tr.assessment_id,tr.visible_at,tr.body_hash,'unavailable' availability,'policy-excluded' reason "
            "FROM interview_turn_results tr JOIN interview_runs r ON r.id=tr.run_id AND r.owner_id=tr.owner_id "
            "WHERE tr.owner_id=:owner_id AND (:goal_id IS NULL OR r.goal_id=:goal_id) ORDER BY tr.run_id,tr.visible_at,tr.id"
        )
        provider_requests = rows(
            "SELECT id,goal_id,job_id,purpose,provider,adapter_version,contract_version,context_ref_hash,disclosure_id,lifecycle,diagnostic_classification,created_at,started_at,completed_at "
            "FROM provider_requests WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY created_at,id"
        )
        quarantines = rows(
            "SELECT q.id,q.provider_request_id,q.job_id,q.raw_output_hash,q.expected_schema_version,p.diagnostic_classification AS failure_classification,q.created_at,"
            "'unavailable' availability,'policy-excluded' reason FROM schema_quarantines q JOIN provider_requests p ON p.id=q.provider_request_id AND p.owner_id=q.owner_id "
            "WHERE q.owner_id=:owner_id AND (:goal_id IS NULL OR p.goal_id=:goal_id) ORDER BY q.created_at,q.id"
        )
        runners = rows(
            "SELECT id,goal_id,artifact_id,job_id,confirmation_id,language,capability,operation,toolchain,working_directory_policy,environment_policy_version,limits_config_version,state,cleanup_state,limit_classification,created_at,updated_at "
            "FROM runner_records WHERE owner_id=:owner_id AND (:goal_id IS NULL OR goal_id=:goal_id) ORDER BY created_at,id"
        )
        runner_inputs = rows(
            "SELECT i.id,i.runner_id,i.logical_path,i.declared_type,i.content_hash,'unavailable' availability,'policy-excluded' reason "
            "FROM runner_inputs i JOIN runner_records r ON r.id=i.runner_id AND r.owner_id=i.owner_id "
            "WHERE i.owner_id=:owner_id AND (:goal_id IS NULL OR r.goal_id=:goal_id) ORDER BY i.runner_id,i.logical_path,i.id"
        )
        runner_outputs = rows(
            "SELECT c.id,c.runner_id,c.phase,c.stream,c.sequence,c.ordinal,c.content_hash,c.truncated,c.created_at,'unavailable' availability,'policy-excluded' reason "
            "FROM runner_output_chunks c JOIN runner_records r ON r.id=c.runner_id AND r.owner_id=c.owner_id "
            "WHERE c.owner_id=:owner_id AND (:goal_id IS NULL OR r.goal_id=:goal_id) ORDER BY c.runner_id,c.ordinal,c.id"
        )
        return {
            "profile": profile,
            "goals": goals,
            "graph_pins": [
                {"goal_id": goal["id"], "graph_version_id": goal["graph_version_id"]}
                for goal in goals
            ],
            "overlays": {
                "personal": personal_overlays,
                "entries": overlay_entries,
                "proposals": overlay_proposals,
            },
            "evidence": evidence,
            "notebook": notebook,
            "review": {
                "preferences": review_preferences,
                "items": review_items,
                "attempts": review_attempts,
            },
            "diagnostics": {"sessions": diagnostics},
            "imports": {
                "records": import_records,
                "statements": import_statements,
                "decisions": import_decisions,
                "mappings": import_mappings,
            },
            "generated_artifacts": generated_artifacts,
            "artifact_provenance": {
                "snapshots": provenance_snapshots,
                "references": provenance_refs,
            },
            "provenance": {
                "sources": sources,
                "snapshots": source_snapshots,
                "claims": claims,
                "citations": citations,
            },
            "interview_transcripts": {
                "runs": interview_runs,
                "turns": interview_turns,
                "results": interview_results,
            },
            "provider": {
                "requests": provider_requests,
                "quarantines": quarantines,
            },
            "runner": {
                "runs": runners,
                "inputs": runner_inputs,
                "output_chunks": runner_outputs,
            },
        }

    def get_export_package(self, owner_id: str, operation_id: str) -> str | None:
        return self._session.scalar(
            select(ExportPackageBodyRow.package_json).where(
                ExportPackageBodyRow.owner_id == owner_id,
                ExportPackageBodyRow.operation_id == operation_id,
            )
        )

    def expire_export_package(
        self, owner_id: str, operation_id: str, updated_at: str
    ) -> None:
        self._session.execute(
            delete(ExportPackageBodyRow).where(
                ExportPackageBodyRow.owner_id == owner_id,
                ExportPackageBodyRow.operation_id == operation_id,
            )
        )
        self._session.execute(
            update(ExportOperationRow)
            .where(
                ExportOperationRow.owner_id == owner_id,
                ExportOperationRow.id == operation_id,
                ExportOperationRow.status == "complete",
            )
            .values(status="expired", updated_at=updated_at)
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


def _decode_json_fields(rows: list[dict[str, Any]], *fields: str) -> None:
    for row in rows:
        for field in fields:
            value = row.get(field)
            row[field.removesuffix("_json")] = (
                json.loads(value) if value is not None else None
            )
            del row[field]

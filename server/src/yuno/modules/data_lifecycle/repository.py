"""SQLite implementation of policy 1.0 retention primitives."""

from __future__ import annotations

from sqlalchemy import delete, func, select, text, update

from yuno.modules.data_lifecycle.domain import (
    CleanupIntent,
    CleanupIntentKind,
    CleanupIntentStatus,
)
from yuno.modules.data_lifecycle.models import (
    DiagnosticAnswerBodyRow,
    DiagnosticPreviewEditBodyRow,
    DiagnosticSessionBodyRow,
    ExportPackageBodyRow,
    FileCleanupIntentRow,
    InterviewRunBodyRow,
    InterviewTurnBodyRow,
    InterviewTurnResultBodyRow,
    JobBodyRow,
)
from yuno.modules.diagnostics.models import DiagnosticSessionRow
from yuno.modules.interview.models import (
    InterviewRunRow,
    InterviewTurnResultRow,
    InterviewTurnRow,
)
from yuno.modules.jobs_events.models import JobAttemptRow, JobResultRow, JobRow
from yuno.modules.runner.models import (
    RunnerConfirmationInputBodyRow,
    RunnerConfirmationInputRow,
    RunnerInputBodyRow,
    RunnerInputRow,
    RunnerOutputChunkBodyRow,
    RunnerOutputChunkRow,
    RunnerRecordBodyRow,
    RunnerRecordRow,
)
from yuno.modules.settings_data.models import ExportOperationRow
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id
from yuno.shared.infrastructure.repository import SqlAlchemyRepository


class SqlAlchemyDataLifecycleRepository(SqlAlchemyRepository):
    def record_workspace(
        self,
        *,
        owner_id: str,
        goal_id: str | None,
        path_ref: str,
        failure_classification: str | None,
        created_at: str,
    ) -> None:
        self.add_cleanup_intent(
            CleanupIntent(
                new_id(),
                owner_id,
                goal_id,
                CleanupIntentKind.RUNNER_WORKSPACE,
                path_ref,
                hash_payload(path_ref),
                CleanupIntentStatus.PENDING,
                failure_classification,
                0,
                created_at,
                created_at,
                None,
            )
        )

    def expire_diagnostics(self, owner_id: str, cutoff: str, expired_at: str) -> int:
        session_ids = select(DiagnosticSessionRow.id).where(
            DiagnosticSessionRow.owner_id == owner_id,
            DiagnosticSessionRow.updated_at <= cutoff,
            DiagnosticSessionRow.state.not_in(("confirmed", "expired")),
        )
        count = self._delete_for_ids(
            DiagnosticAnswerBodyRow,
            "answer_id",
            select(text("id"))
            .select_from(text("diagnostic_answers"))
            .where(
                text(
                    "owner_id=:owner_id AND session_id IN (SELECT id FROM diagnostic_sessions WHERE owner_id=:owner_id AND updated_at <= :cutoff AND state NOT IN ('confirmed','expired'))"
                )
            )
            .params(owner_id=owner_id, cutoff=cutoff),
        )
        self._session.execute(
            delete(DiagnosticPreviewEditBodyRow).where(
                DiagnosticPreviewEditBodyRow.owner_id == owner_id,
                DiagnosticPreviewEditBodyRow.edit_id.in_(
                    select(text("id"))
                    .select_from(text("diagnostic_preview_edits"))
                    .where(
                        text(
                            "session_id IN (SELECT id FROM diagnostic_sessions WHERE owner_id=:owner_id AND updated_at <= :cutoff AND state NOT IN ('confirmed','expired'))"
                        )
                    )
                    .params(owner_id=owner_id, cutoff=cutoff)
                ),
            )
        )
        self._session.execute(
            delete(DiagnosticSessionBodyRow).where(
                DiagnosticSessionBodyRow.owner_id == owner_id,
                DiagnosticSessionBodyRow.session_id.in_(session_ids),
            )
        )
        result = self._session.execute(
            update(DiagnosticSessionRow)
            .where(DiagnosticSessionRow.id.in_(session_ids))
            .values(state="expired", expires_at=expired_at, updated_at=expired_at)
        )
        return max(count, result.rowcount or 0)

    def expire_interviews(self, owner_id: str, cutoff: str) -> int:
        run_ids = select(InterviewRunRow.id).where(
            InterviewRunRow.owner_id == owner_id,
            InterviewRunRow.updated_at <= cutoff,
            InterviewRunRow.state.in_(
                (
                    "ready",
                    "answering",
                    "follow-up",
                    "paused",
                    "submitted",
                    "evaluating",
                    "completing",
                    "failed-recoverable",
                )
            ),
        )
        result = self._session.execute(
            delete(InterviewRunBodyRow).where(
                InterviewRunBodyRow.owner_id == owner_id,
                InterviewRunBodyRow.run_id.in_(run_ids),
            )
        )
        turn_ids = select(InterviewTurnRow.id).where(
            InterviewTurnRow.owner_id == owner_id, InterviewTurnRow.run_id.in_(run_ids)
        )
        result_ids = select(InterviewTurnResultRow.id).where(
            InterviewTurnResultRow.owner_id == owner_id,
            InterviewTurnResultRow.run_id.in_(run_ids),
        )
        self._session.execute(
            delete(InterviewTurnBodyRow).where(
                InterviewTurnBodyRow.owner_id == owner_id,
                InterviewTurnBodyRow.turn_id.in_(turn_ids),
            )
        )
        self._session.execute(
            delete(InterviewTurnResultBodyRow).where(
                InterviewTurnResultBodyRow.owner_id == owner_id,
                InterviewTurnResultBodyRow.result_id.in_(result_ids),
            )
        )
        return result.rowcount or 0

    def purge_job_exhaust(self, owner_id: str, cutoff: str) -> int:
        job_ids = select(JobRow.id).where(
            JobRow.owner_id == owner_id,
            JobRow.terminal_at.is_not(None),
            JobRow.terminal_at <= cutoff,
            text(
                "NOT EXISTS (SELECT 1 FROM export_operations e WHERE e.owner_id=jobs.owner_id AND e.job_id=jobs.id AND e.status IN ('queued','running'))"
            ),
            text(
                "NOT EXISTS (SELECT 1 FROM delete_operations d WHERE d.owner_id=jobs.owner_id AND d.job_id=jobs.id AND d.status IN ('preflight','queued','running'))"
            ),
            text(
                "(jobs.state IN ('failed','cancelled') OR EXISTS (SELECT 1 FROM job_results r WHERE r.owner_id=jobs.owner_id AND r.job_id=jobs.id))"
            ),
        )
        count = (
            self._session.scalar(select(func.count()).select_from(job_ids.subquery()))
            or 0
        )
        runner_ids = select(RunnerRecordRow.id).where(
            RunnerRecordRow.owner_id == owner_id,
            RunnerRecordRow.job_id.in_(job_ids),
        )
        confirmation_ids = select(RunnerRecordRow.confirmation_id).where(
            RunnerRecordRow.owner_id == owner_id,
            RunnerRecordRow.job_id.in_(job_ids),
        )
        self._session.execute(
            delete(RunnerConfirmationInputBodyRow).where(
                RunnerConfirmationInputBodyRow.owner_id == owner_id,
                RunnerConfirmationInputBodyRow.input_id.in_(
                    select(RunnerConfirmationInputRow.id).where(
                        RunnerConfirmationInputRow.owner_id == owner_id,
                        RunnerConfirmationInputRow.confirmation_id.in_(
                            confirmation_ids
                        ),
                    )
                ),
            )
        )
        self._session.execute(
            delete(RunnerInputBodyRow).where(
                RunnerInputBodyRow.owner_id == owner_id,
                RunnerInputBodyRow.input_id.in_(
                    select(RunnerInputRow.id).where(
                        RunnerInputRow.owner_id == owner_id,
                        RunnerInputRow.runner_id.in_(runner_ids),
                    )
                ),
            )
        )
        self._session.execute(
            delete(RunnerRecordBodyRow).where(
                RunnerRecordBodyRow.owner_id == owner_id,
                RunnerRecordBodyRow.runner_id.in_(runner_ids),
            )
        )
        self._session.execute(
            delete(JobBodyRow).where(
                JobBodyRow.owner_id == owner_id, JobBodyRow.job_id.in_(job_ids)
            )
        )
        self._session.execute(
            delete(JobAttemptRow).where(
                JobAttemptRow.owner_id == owner_id,
                JobAttemptRow.job_id.in_(job_ids),
            )
        )
        self._session.execute(
            delete(JobResultRow).where(
                JobResultRow.owner_id == owner_id,
                JobResultRow.job_id.in_(job_ids),
            )
        )
        return count

    def expire_job_events(self, owner_id: str, cutoff: str, keep_newest: int) -> int:
        result = self._session.execute(
            text(
                "DELETE FROM job_events WHERE owner_id=:owner_id AND (created_at <= :cutoff OR sequence NOT IN (SELECT sequence FROM job_events WHERE owner_id=:owner_id ORDER BY sequence DESC LIMIT :keep_newest)) AND job_id IN (SELECT id FROM jobs WHERE owner_id=:owner_id AND terminal_at IS NOT NULL)"
            ),
            {"owner_id": owner_id, "cutoff": cutoff, "keep_newest": keep_newest},
        )
        return result.rowcount or 0

    def expire_runner_outputs(self, owner_id: str, cutoff: str) -> int:
        chunk_ids = (
            select(RunnerOutputChunkRow.id)
            .join(RunnerRecordRow, RunnerRecordRow.id == RunnerOutputChunkRow.runner_id)
            .join(JobRow, JobRow.id == RunnerRecordRow.job_id)
            .where(
                RunnerOutputChunkRow.owner_id == owner_id,
                JobRow.owner_id == owner_id,
                JobRow.terminal_at.is_not(None),
                JobRow.terminal_at <= cutoff,
                RunnerRecordRow.state.in_(
                    ("completed", "failed", "timed-out-or-limited", "cancelled")
                ),
            )
        )
        result = self._session.execute(
            delete(RunnerOutputChunkBodyRow).where(
                RunnerOutputChunkBodyRow.owner_id == owner_id,
                RunnerOutputChunkBodyRow.chunk_id.in_(chunk_ids),
            )
        )
        return result.rowcount or 0

    def expire_export_packages(self, owner_id: str, cutoff: str) -> int:
        operation_ids = select(ExportOperationRow.id).where(
            ExportOperationRow.owner_id == owner_id,
            ExportOperationRow.package_expires_at.is_not(None),
            ExportOperationRow.package_expires_at <= cutoff,
        )
        result = self._session.execute(
            delete(ExportPackageBodyRow).where(
                ExportPackageBodyRow.owner_id == owner_id,
                ExportPackageBodyRow.operation_id.in_(operation_ids),
            )
        )
        self._session.execute(
            update(ExportOperationRow)
            .where(
                ExportOperationRow.id.in_(operation_ids),
                ExportOperationRow.status == "complete",
            )
            .values(status="expired", updated_at=cutoff)
        )
        return result.rowcount or 0

    def expire_export_operations(self, owner_id: str, cutoff: str) -> int:
        result = self._session.execute(
            delete(ExportOperationRow).where(
                ExportOperationRow.owner_id == owner_id,
                ExportOperationRow.metadata_expires_at.is_not(None),
                ExportOperationRow.metadata_expires_at <= cutoff,
            )
        )
        return result.rowcount or 0

    def purge_goal_bodies(self, owner_id: str, goal_id: str, now: str) -> int:
        references = self._session.execute(
            text("""
            SELECT 'source-snapshot' kind, b.content_ref path_ref FROM source_snapshot_bodies b
            JOIN source_snapshots s ON s.id=b.snapshot_id AND s.owner_id=b.owner_id
            WHERE b.owner_id=:owner_id AND s.source_id IN (SELECT DISTINCT source_id FROM citations WHERE owner_id=:owner_id AND goal_id=:goal_id)
            AND NOT EXISTS (
              SELECT 1 FROM citations other
              JOIN goal_workspaces g ON g.id=other.goal_id AND g.owner_id=other.owner_id
              WHERE other.owner_id=:owner_id AND other.source_snapshot_id=s.id
                AND other.goal_id!=:goal_id AND g.status!='tombstoned'
            )
            UNION ALL
            SELECT 'provider-quarantine', b.raw_output_ref FROM schema_quarantine_bodies b
            JOIN schema_quarantines q ON q.id=b.quarantine_id AND q.owner_id=b.owner_id
            WHERE b.owner_id=:owner_id AND q.provider_request_id IN (SELECT id FROM provider_requests WHERE owner_id=:owner_id AND goal_id=:goal_id)
            """),
            {"owner_id": owner_id, "goal_id": goal_id},
        ).mappings()
        for reference in references:
            path_ref = reference["path_ref"]
            if path_ref:
                self._session.add(
                    FileCleanupIntentRow(
                        id=new_id(),
                        owner_id=owner_id,
                        goal_id=goal_id,
                        kind=reference["kind"],
                        path_ref=path_ref,
                        path_hash=hash_payload(path_ref),
                        status="pending",
                        failure_classification=None,
                        attempts=0,
                        created_at=now,
                        updated_at=now,
                        completed_at=None,
                    )
                )
        statements = (
            "DELETE FROM profiles_goals_idempotency_bodies WHERE owner_id=:owner_id",
            "DELETE FROM roadmap_idempotency_bodies WHERE owner_id=:owner_id",
            "DELETE FROM diagnostics_idempotency_bodies WHERE owner_id=:owner_id",
            "DELETE FROM imports_idempotency_bodies WHERE owner_id=:owner_id",
            "DELETE FROM interview_idempotency_bodies WHERE owner_id=:owner_id",
            "DELETE FROM notebook_review_idempotency_bodies WHERE owner_id=:owner_id",
            "DELETE FROM evidence_evaluation_idempotency_bodies WHERE owner_id=:owner_id",
            "DELETE FROM learning_content_idempotency_bodies WHERE owner_id=:owner_id",
            "DELETE FROM merge_item_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM canonical_merge_followup_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM interview_bundle_item_bodies WHERE owner_id=:owner_id AND item_id IN (SELECT i.id FROM interview_bundle_items i JOIN interview_bundles b ON b.id=i.bundle_id AND b.owner_id=i.owner_id WHERE b.owner_id=:owner_id AND b.goal_id=:goal_id)",
            "DELETE FROM interview_bundle_bodies WHERE owner_id=:owner_id AND bundle_id IN (SELECT id FROM interview_bundles WHERE owner_id=:owner_id AND goal_id=:goal_id)",
            "DELETE FROM goal_workspace_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM evidence_summary_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM assessment_dimension_result_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM assessment_dispute_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM assessment_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM goal_progress_memo_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM notebook_entry_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM review_item_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM review_attempt_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM hands_on_cross_question_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM hands_on_review_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM hands_on_artifact_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM hands_on_work_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM claim_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM citation_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM provider_request_bodies WHERE owner_id=:owner_id AND request_id IN (SELECT id FROM provider_requests WHERE owner_id=:owner_id AND goal_id=:goal_id)",
            "DELETE FROM schema_quarantine_bodies WHERE owner_id=:owner_id AND quarantine_id IN (SELECT q.id FROM schema_quarantines q JOIN provider_requests p ON p.id=q.provider_request_id AND p.owner_id=q.owner_id WHERE p.owner_id=:owner_id AND p.goal_id=:goal_id)",
            "DELETE FROM search_document_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM source_snapshot_bodies WHERE owner_id=:owner_id AND snapshot_id IN (SELECT DISTINCT c.source_snapshot_id FROM citations c WHERE c.owner_id=:owner_id AND c.goal_id=:goal_id AND c.source_snapshot_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM citations other JOIN goal_workspaces g ON g.id=other.goal_id AND g.owner_id=other.owner_id WHERE other.owner_id=:owner_id AND other.source_snapshot_id=c.source_snapshot_id AND other.goal_id!=:goal_id AND g.status!='tombstoned'))",
            "DELETE FROM overlay_entry_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM overlay_proposal_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM overlay_proposal_decision_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM learning_state_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM learner_correction_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM transferred_evidence_ref_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM job_attempt_bodies WHERE owner_id=:owner_id AND attempt_id IN (SELECT a.id FROM job_attempts a JOIN jobs j ON j.id=a.job_id AND j.owner_id=a.owner_id WHERE j.owner_id=:owner_id AND j.goal_id=:goal_id)",
            "DELETE FROM job_result_bodies WHERE owner_id=:owner_id AND result_id IN (SELECT r.id FROM job_results r JOIN jobs j ON j.id=r.job_id AND j.owner_id=r.owner_id WHERE j.owner_id=:owner_id AND j.goal_id=:goal_id)",
            "DELETE FROM job_bodies WHERE owner_id=:owner_id AND job_id IN (SELECT id FROM jobs WHERE owner_id=:owner_id AND goal_id=:goal_id)",
            "UPDATE jobs SET retryable=0,request_ref=NULL,disclosure_ref=NULL,confirmation_ref=NULL,substitution_ref=NULL,worker_id=NULL,updated_at=:now WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM export_package_bodies WHERE owner_id=:owner_id AND operation_id IN (SELECT id FROM export_operations WHERE owner_id=:owner_id AND (goal_id=:goal_id OR goal_id IS NULL))",
            "UPDATE export_operations SET status='expired',updated_at=:now WHERE owner_id=:owner_id AND (goal_id=:goal_id OR goal_id IS NULL) AND status='complete'",
            "DELETE FROM diagnostic_answer_bodies WHERE owner_id=:owner_id AND answer_id IN (SELECT a.id FROM diagnostic_answers a JOIN diagnostic_sessions s ON s.id=a.session_id WHERE s.owner_id=:owner_id AND s.confirmed_goal_id=:goal_id)",
            "DELETE FROM diagnostic_preview_edit_bodies WHERE owner_id=:owner_id AND edit_id IN (SELECT e.id FROM diagnostic_preview_edits e JOIN diagnostic_sessions s ON s.id=e.session_id WHERE s.owner_id=:owner_id AND s.confirmed_goal_id=:goal_id)",
            "DELETE FROM diagnostic_session_bodies WHERE owner_id=:owner_id AND session_id IN (SELECT id FROM diagnostic_sessions WHERE owner_id=:owner_id AND confirmed_goal_id=:goal_id)",
            "DELETE FROM import_statement_decision_bodies WHERE owner_id=:owner_id AND decision_id IN (SELECT d.id FROM import_statement_decisions d JOIN import_statements s ON s.id=d.statement_id JOIN import_records i ON i.id=s.import_id WHERE i.owner_id=:owner_id AND i.goal_id=:goal_id)",
            "DELETE FROM import_statement_bodies WHERE owner_id=:owner_id AND statement_id IN (SELECT s.id FROM import_statements s JOIN import_records i ON i.id=s.import_id WHERE i.owner_id=:owner_id AND i.goal_id=:goal_id)",
            "DELETE FROM import_record_bodies WHERE owner_id=:owner_id AND import_id IN (SELECT id FROM import_records WHERE owner_id=:owner_id AND goal_id=:goal_id)",
            "DELETE FROM generated_artifact_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM topic_conversation_turn_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM interview_run_bodies WHERE owner_id=:owner_id AND goal_id=:goal_id",
            "DELETE FROM interview_turn_bodies WHERE owner_id=:owner_id AND turn_id IN (SELECT t.id FROM interview_turns t JOIN interview_runs r ON r.id=t.run_id WHERE r.owner_id=:owner_id AND r.goal_id=:goal_id)",
            "DELETE FROM interview_turn_result_bodies WHERE owner_id=:owner_id AND result_id IN (SELECT x.id FROM interview_turn_results x JOIN interview_runs r ON r.id=x.run_id WHERE r.owner_id=:owner_id AND r.goal_id=:goal_id)",
            "DELETE FROM runner_confirmation_input_bodies WHERE owner_id=:owner_id AND input_id IN (SELECT i.id FROM runner_confirmation_inputs i JOIN runner_confirmations c ON c.id=i.confirmation_id WHERE c.owner_id=:owner_id AND c.goal_id=:goal_id)",
            "DELETE FROM runner_input_bodies WHERE owner_id=:owner_id AND input_id IN (SELECT i.id FROM runner_inputs i JOIN runner_records r ON r.id=i.runner_id WHERE r.owner_id=:owner_id AND r.goal_id=:goal_id)",
            "DELETE FROM runner_output_chunk_bodies WHERE owner_id=:owner_id AND chunk_id IN (SELECT c.id FROM runner_output_chunks c JOIN runner_records r ON r.id=c.runner_id WHERE r.owner_id=:owner_id AND r.goal_id=:goal_id)",
            "DELETE FROM runner_record_bodies WHERE owner_id=:owner_id AND runner_id IN (SELECT id FROM runner_records WHERE owner_id=:owner_id AND goal_id=:goal_id)",
        )
        total = 0
        for statement in statements:
            total += (
                self._session.execute(
                    text(statement),
                    {"owner_id": owner_id, "goal_id": goal_id, "now": now},
                ).rowcount
                or 0
            )
        return total

    def purge_import_bodies(self, owner_id: str, import_id: str) -> int:
        parameters = {"owner_id": owner_id, "import_id": import_id}
        statements = (
            "DELETE FROM import_statement_decision_bodies WHERE owner_id=:owner_id AND decision_id IN (SELECT d.id FROM import_statement_decisions d JOIN import_statements s ON s.id=d.statement_id WHERE s.owner_id=:owner_id AND s.import_id=:import_id)",
            "DELETE FROM import_statement_bodies WHERE owner_id=:owner_id AND statement_id IN (SELECT id FROM import_statements WHERE owner_id=:owner_id AND import_id=:import_id)",
            "DELETE FROM import_record_bodies WHERE owner_id=:owner_id AND import_id=:import_id",
        )
        return sum(
            self._session.execute(text(statement), parameters).rowcount or 0
            for statement in statements
        )

    def purge_interview_bodies(self, owner_id: str, run_id: str) -> int:
        parameters = {"owner_id": owner_id, "run_id": run_id}
        statements = (
            "DELETE FROM interview_turn_result_bodies WHERE owner_id=:owner_id AND result_id IN (SELECT id FROM interview_turn_results WHERE owner_id=:owner_id AND run_id=:run_id)",
            "DELETE FROM interview_turn_bodies WHERE owner_id=:owner_id AND turn_id IN (SELECT id FROM interview_turns WHERE owner_id=:owner_id AND run_id=:run_id)",
            "DELETE FROM interview_run_bodies WHERE owner_id=:owner_id AND run_id=:run_id",
        )
        return sum(
            self._session.execute(text(statement), parameters).rowcount or 0
            for statement in statements
        )

    def add_cleanup_intent(self, intent: CleanupIntent) -> None:
        self._session.add(
            FileCleanupIntentRow(
                **{
                    **intent.__dict__,
                    "kind": intent.kind.value,
                    "status": intent.status.value,
                }
            )
        )

    def list_pending_cleanup_intents(self, owner_id: str) -> tuple[CleanupIntent, ...]:
        rows = self._session.scalars(
            select(FileCleanupIntentRow)
            .where(
                FileCleanupIntentRow.owner_id == owner_id,
                FileCleanupIntentRow.status.in_(("pending", "failed")),
            )
            .order_by(FileCleanupIntentRow.created_at, FileCleanupIntentRow.id)
        ).all()
        return tuple(_intent(row) for row in rows)

    def finish_cleanup_intent(
        self, owner_id: str, intent_id: str, completed_at: str
    ) -> bool:
        result = self._session.execute(
            update(FileCleanupIntentRow)
            .where(
                FileCleanupIntentRow.owner_id == owner_id,
                FileCleanupIntentRow.id == intent_id,
            )
            .values(
                status="complete",
                failure_classification=None,
                attempts=FileCleanupIntentRow.attempts + 1,
                updated_at=completed_at,
                completed_at=completed_at,
            )
        )
        return result.rowcount == 1

    def fail_cleanup_intent(
        self, owner_id: str, intent_id: str, classification: str, updated_at: str
    ) -> bool:
        result = self._session.execute(
            update(FileCleanupIntentRow)
            .where(
                FileCleanupIntentRow.owner_id == owner_id,
                FileCleanupIntentRow.id == intent_id,
            )
            .values(
                status="failed",
                failure_classification=classification,
                attempts=FileCleanupIntentRow.attempts + 1,
                updated_at=updated_at,
            )
        )
        return result.rowcount == 1

    def _delete_for_ids(self, model: type, column: str, ids: object) -> int:
        result = self._session.execute(
            delete(model).where(getattr(model, column).in_(ids))
        )
        return result.rowcount or 0


def _intent(row: FileCleanupIntentRow) -> CleanupIntent:
    return CleanupIntent(
        row.id,
        row.owner_id,
        row.goal_id,
        CleanupIntentKind(row.kind),
        row.path_ref,
        row.path_hash,
        CleanupIntentStatus(row.status),
        row.failure_classification,
        row.attempts,
        row.created_at,
        row.updated_at,
        row.completed_at,
    )

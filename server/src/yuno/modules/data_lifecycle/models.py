"""Removable sensitive bodies and durable file-cleanup intents."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    LargeBinary,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from yuno.shared.infrastructure.base import Base, id_column, utc_timestamp_column


class _OwnedBody:
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)


def _idempotency_body(name: str, parent: str) -> type[Base]:
    return type(
        name,
        (_OwnedBody, Base),
        {
            "__tablename__": parent + "_bodies",
            "idempotency_id": mapped_column(Text, primary_key=True),
            "response_json": mapped_column(Text, nullable=False),
            "__table_args__": (
                ForeignKeyConstraint(
                    ["idempotency_id"], [f"{parent}.id"], ondelete="CASCADE"
                ),
                CheckConstraint(
                    "json_valid(response_json)", name="response_json_valid"
                ),
            ),
        },
    )


ProfilesGoalsIdempotencyBodyRow = _idempotency_body(
    "ProfilesGoalsIdempotencyBodyRow", "profiles_goals_idempotency"
)
RoadmapIdempotencyBodyRow = _idempotency_body(
    "RoadmapIdempotencyBodyRow", "roadmap_idempotency"
)
DiagnosticsIdempotencyBodyRow = _idempotency_body(
    "DiagnosticsIdempotencyBodyRow", "diagnostics_idempotency"
)
ImportsIdempotencyBodyRow = _idempotency_body(
    "ImportsIdempotencyBodyRow", "imports_idempotency"
)
InterviewIdempotencyBodyRow = _idempotency_body(
    "InterviewIdempotencyBodyRow", "interview_idempotency"
)
NotebookReviewIdempotencyBodyRow = _idempotency_body(
    "NotebookReviewIdempotencyBodyRow", "notebook_review_idempotency"
)
EvidenceEvaluationIdempotencyBodyRow = _idempotency_body(
    "EvidenceEvaluationIdempotencyBodyRow", "evidence_evaluation_idempotency"
)
LearningContentIdempotencyBodyRow = _idempotency_body(
    "LearningContentIdempotencyBodyRow", "learning_content_idempotency"
)


class LearnerProfileBodyRow(_OwnedBody, Base):
    __tablename__ = "learner_profile_bodies"
    owner_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("learner_profiles.owner_id", ondelete="CASCADE"),
        primary_key=True,
    )
    experience: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[str | None] = mapped_column(Text)
    weaknesses: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (ForeignKeyConstraint(["owner_id"], ["owners.id"]),)


class GoalWorkspaceBodyRow(_OwnedBody, Base):
    __tablename__ = "goal_workspace_bodies"
    goal_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    resume_position: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "role IS NULL OR length(trim(role)) > 0", name="role_non_blank"
        ),
    )


class OverlayEntryBodyRow(_OwnedBody, Base):
    __tablename__ = "overlay_entry_bodies"
    entry_id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["entry_id", "owner_id", "goal_id"],
            [
                "overlay_entries.id",
                "overlay_entries.owner_id",
                "overlay_entries.goal_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("json_valid(value_json)", name="value_json_valid"),
    )


class OverlayProposalBodyRow(_OwnedBody, Base):
    __tablename__ = "overlay_proposal_bodies"
    proposal_id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    state_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["proposal_id", "owner_id", "goal_id"],
            [
                "overlay_proposals.id",
                "overlay_proposals.owner_id",
                "overlay_proposals.goal_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("json_valid(payload_json)", name="payload_json_valid"),
    )


class OverlayProposalDecisionBodyRow(_OwnedBody, Base):
    __tablename__ = "overlay_proposal_decision_bodies"
    decision_id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["decision_id", "owner_id", "goal_id"],
            [
                "overlay_proposal_decisions.id",
                "overlay_proposal_decisions.owner_id",
                "overlay_proposal_decisions.goal_id",
            ],
            ondelete="CASCADE",
        ),
    )


class LearningStateBodyRow(_OwnedBody, Base):
    __tablename__ = "learning_state_bodies"
    state_id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["state_id", "owner_id", "goal_id"],
            [
                "learning_states.id",
                "learning_states.owner_id",
                "learning_states.goal_id",
            ],
            ondelete="CASCADE",
        ),
    )


class LearnerCorrectionBodyRow(_OwnedBody, Base):
    __tablename__ = "learner_correction_bodies"
    correction_id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["correction_id", "owner_id", "goal_id"],
            [
                "learner_corrections.id",
                "learner_corrections.owner_id",
                "learner_corrections.goal_id",
            ],
            ondelete="CASCADE",
        ),
    )


class TransferredEvidenceRefBodyRow(_OwnedBody, Base):
    __tablename__ = "transferred_evidence_ref_bodies"
    transfer_id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["transfer_id", "owner_id", "goal_id"],
            [
                "transferred_evidence_refs.id",
                "transferred_evidence_refs.owner_id",
                "transferred_evidence_refs.goal_id",
            ],
            ondelete="CASCADE",
        ),
    )


class DiagnosticSessionBodyRow(_OwnedBody, Base):
    __tablename__ = "diagnostic_session_bodies"
    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    setup_inputs_json: Mapped[str] = mapped_column(Text, nullable=False)
    untrusted_seed_text: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "owner_id"],
            ["diagnostic_sessions.id", "diagnostic_sessions.owner_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "json_valid(setup_inputs_json) AND json_type(setup_inputs_json)='object'",
            name="setup_inputs_json_valid",
        ),
    )


class DiagnosticAnswerBodyRow(_OwnedBody, Base):
    __tablename__ = "diagnostic_answer_bodies"
    answer_id: Mapped[str] = mapped_column(Text, primary_key=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["answer_id", "owner_id"],
            ["diagnostic_answers.id", "diagnostic_answers.owner_id"],
            ondelete="CASCADE",
        ),
    )


class DiagnosticPreviewEditBodyRow(_OwnedBody, Base):
    __tablename__ = "diagnostic_preview_edit_bodies"
    edit_id: Mapped[str] = mapped_column(Text, primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["edit_id", "owner_id"],
            ["diagnostic_preview_edits.id", "diagnostic_preview_edits.owner_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "json_valid(value_json) AND json_type(value_json)='object'",
            name="value_json_valid",
        ),
    )


class ImportRecordBodyRow(_OwnedBody, Base):
    __tablename__ = "import_record_bodies"
    import_id: Mapped[str] = mapped_column(Text, primary_key=True)
    original_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["import_id", "owner_id"],
            ["import_records.id", "import_records.owner_id"],
            ondelete="CASCADE",
        ),
    )


class ImportStatementBodyRow(_OwnedBody, Base):
    __tablename__ = "import_statement_bodies"
    statement_id: Mapped[str] = mapped_column(Text, primary_key=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["statement_id", "owner_id"],
            ["import_statements.id", "import_statements.owner_id"],
            ondelete="CASCADE",
        ),
    )


class ImportStatementDecisionBodyRow(_OwnedBody, Base):
    __tablename__ = "import_statement_decision_bodies"
    decision_id: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["decision_id", "owner_id"],
            ["import_statement_decisions.id", "import_statement_decisions.owner_id"],
            ondelete="CASCADE",
        ),
    )


class GeneratedArtifactBodyRow(_OwnedBody, Base):
    __tablename__ = "generated_artifact_bodies"
    artifact_id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    body_ref: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "generated_artifacts.id",
                "generated_artifacts.owner_id",
                "generated_artifacts.goal_id",
            ],
            ondelete="CASCADE",
        ),
    )


class TopicConversationTurnBodyRow(_OwnedBody, Base):
    __tablename__ = "topic_conversation_turn_bodies"
    turn_id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["turn_id", "owner_id", "goal_id"],
            [
                "topic_conversation_turns.id",
                "topic_conversation_turns.owner_id",
                "topic_conversation_turns.goal_id",
            ],
            ondelete="CASCADE",
        ),
    )


class InterviewRunBodyRow(_OwnedBody, Base):
    __tablename__ = "interview_run_bodies"
    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    hint_text: Mapped[str | None] = mapped_column(Text)
    draft: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "owner_id", "goal_id"],
            ["interview_runs.id", "interview_runs.owner_id", "interview_runs.goal_id"],
            ondelete="CASCADE",
        ),
    )


class InterviewTurnBodyRow(_OwnedBody, Base):
    __tablename__ = "interview_turn_bodies"
    turn_id: Mapped[str] = mapped_column(Text, primary_key=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["turn_id", "owner_id"],
            ["interview_turns.id", "interview_turns.owner_id"],
            ondelete="CASCADE",
        ),
    )


class InterviewTurnResultBodyRow(_OwnedBody, Base):
    __tablename__ = "interview_turn_result_bodies"
    result_id: Mapped[str] = mapped_column(Text, primary_key=True)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    cross_question_candidate: Mapped[str | None] = mapped_column(Text)
    facts_json: Mapped[str] = mapped_column(Text, nullable=False)
    trade_offs_json: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions_json: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["result_id", "owner_id"],
            ["interview_turn_results.id", "interview_turn_results.owner_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "json_valid(facts_json) AND json_valid(trade_offs_json) AND json_valid(dimensions_json)",
            name="result_json_valid",
        ),
    )


class JobBodyRow(_OwnedBody, Base):
    __tablename__ = "job_bodies"
    job_id: Mapped[str] = mapped_column(Text, primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostic: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "owner_id"], ["jobs.id", "jobs.owner_id"], ondelete="CASCADE"
        ),
        CheckConstraint("json_valid(payload_json)", name="payload_json_valid"),
    )


class JobAttemptBodyRow(_OwnedBody, Base):
    __tablename__ = "job_attempt_bodies"
    attempt_id: Mapped[str] = mapped_column(Text, primary_key=True)
    process_identity: Mapped[str | None] = mapped_column(Text)
    pid: Mapped[int | None] = mapped_column()
    pgid: Mapped[int | None] = mapped_column()
    temp_path: Mapped[str | None] = mapped_column(Text)
    diagnostic: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "owner_id"],
            ["job_attempts.id", "job_attempts.owner_id"],
            ondelete="CASCADE",
        ),
    )


class JobResultBodyRow(_OwnedBody, Base):
    __tablename__ = "job_result_bodies"
    result_id: Mapped[str] = mapped_column(Text, primary_key=True)
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostic_ref: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["result_id", "owner_id"],
            ["job_results.id", "job_results.owner_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("json_valid(warnings_json)", name="warnings_json_valid"),
    )


class ExportPackageBodyRow(_OwnedBody, Base):
    __tablename__ = "export_package_bodies"
    operation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    package_json: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["operation_id", "owner_id"],
            ["export_operations.id", "export_operations.owner_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("json_valid(package_json)", name="package_json_valid"),
    )


class FileCleanupIntentRow(Base):
    __tablename__ = "file_cleanup_intents"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_file_cleanup_intents_id_owner"),
        CheckConstraint(
            "kind IN ('runner-workspace','runner-output','generated-artifact','export-package','source-snapshot','provider-quarantine')",
            name="kind_valid",
        ),
        CheckConstraint(
            "status IN ('pending','complete','failed')", name="status_valid"
        ),
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("owners.id"), nullable=False)
    goal_id: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    path_ref: Mapped[str] = mapped_column(Text, nullable=False)
    path_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    failure_classification: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[str] = utc_timestamp_column()
    updated_at: Mapped[str] = utc_timestamp_column()
    completed_at: Mapped[str | None] = utc_timestamp_column(nullable=True)

"""policy 1.0 body separation and retention

Revision ID: e10d1a0c0100
Revises: a9d4e6f1b208
"""

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e10d1a0c0100"
down_revision: str | Sequence[str] | None = "a9d4e6f1b208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "file_cleanup_intents",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("path_ref", sa.Text(), nullable=False),
        sa.Column("path_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failure_classification", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('runner-workspace','runner-output','generated-artifact','export-package','source-snapshot','provider-quarantine')",
            name=op.f("ck_file_cleanup_intents_kind_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','complete','failed')",
            name=op.f("ck_file_cleanup_intents_status_valid"),
        ),
        sa.CheckConstraint(
            "attempts >= 0", name=op.f("ck_file_cleanup_intents_attempts_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_file_cleanup_intents_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_cleanup_intents")),
        sa.UniqueConstraint("id", "owner_id", name="uq_file_cleanup_intents_id_owner"),
    )
    op.create_table(
        "learner_profile_bodies",
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("experience", sa.Text()),
        sa.Column("strengths", sa.Text()),
        sa.Column("weaknesses", sa.Text()),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["learner_profiles.owner_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.PrimaryKeyConstraint("owner_id"),
    )
    op.create_table(
        "goal_workspace_bodies",
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text()),
        sa.Column("role", sa.Text()),
        sa.Column("resume_position", sa.Text()),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("goal_id"),
        sa.CheckConstraint(
            "role IS NULL OR length(trim(role)) > 0", name="role_non_blank"
        ),
    )
    body_table_specs = (
        (
            "overlay_entry_bodies",
            "entry_id",
            "overlay_entries",
            (("value_json", False), ("reason", True)),
        ),
        (
            "overlay_proposal_bodies",
            "proposal_id",
            "overlay_proposals",
            (("payload_json", False), ("state_reason", True)),
        ),
        (
            "overlay_proposal_decision_bodies",
            "decision_id",
            "overlay_proposal_decisions",
            (("reason", True),),
        ),
        (
            "learning_state_bodies",
            "state_id",
            "learning_states",
            (("explanation", False),),
        ),
        (
            "learner_correction_bodies",
            "correction_id",
            "learner_corrections",
            (("value", False), ("reason", True)),
        ),
        (
            "transferred_evidence_ref_bodies",
            "transfer_id",
            "transferred_evidence_refs",
            (("rationale", False),),
        ),
    )
    for table, key, parent, columns in body_table_specs:
        op.create_table(
            table,
            sa.Column(key, sa.Text(), nullable=False),
            sa.Column("owner_id", sa.Text(), nullable=False),
            sa.Column("goal_id", sa.Text(), nullable=False),
            *(
                sa.Column(name, sa.Text(), nullable=nullable)
                for name, nullable in columns
            ),
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
            sa.ForeignKeyConstraint(
                [key, "owner_id", "goal_id"],
                [f"{parent}.id", f"{parent}.owner_id", f"{parent}.goal_id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint(key),
            *(
                (
                    sa.CheckConstraint(
                        "json_valid(value_json)",
                        name=op.f("ck_overlay_entry_bodies_value_json_valid"),
                    ),
                )
                if table == "overlay_entry_bodies"
                else (
                    sa.CheckConstraint(
                        "json_valid(payload_json)",
                        name=op.f("ck_overlay_proposal_bodies_payload_json_valid"),
                    ),
                )
                if table == "overlay_proposal_bodies"
                else ()
            ),
        )
    hash_columns = {
        "evidence": ("summary_hash",),
        "rubrics": ("body_hash",),
        "rubric_dimensions": ("body_hash",),
        "assessments": ("body_hash",),
        "assessment_dimension_results": ("body_hash",),
        "assessment_disputes": ("body_hash",),
        "goal_progress_memos": ("body_hash",),
        "notebook_entries": ("body_hash",),
        "review_items": ("body_hash",),
        "review_attempts": ("body_hash",),
        "hands_on_work": ("body_hash",),
        "hands_on_artifacts": ("body_hash",),
        "hands_on_reviews": ("body_hash",),
        "hands_on_cross_questions": ("body_hash",),
        "sources": ("body_hash",),
        "claims": ("claim_hash",),
        "citations": ("body_hash",),
        "provider_requests": ("body_hash",),
        "schema_quarantines": ("body_hash",),
        "search_documents": ("body_hash",),
        "learner_profiles": ("body_hash",),
        "goal_workspaces": ("body_hash",),
        "overlay_proposal_decisions": ("body_hash",),
        "learning_states": ("body_hash",),
        "learner_corrections": ("body_hash",),
        "transferred_evidence_refs": ("body_hash",),
        "diagnostic_sessions": ("setup_inputs_hash", "untrusted_seed_hash"),
        "diagnostic_answers": ("answer_hash",),
        "diagnostic_preview_edits": ("body_hash",),
        "import_statements": ("corrected_hash",),
        "import_statement_decisions": ("value_hash",),
        "interview_runs": ("body_hash",),
        "interview_turns": ("body_hash",),
        "interview_turn_results": ("body_hash",),
        "topic_conversation_turns": ("body_hash",),
        "runner_output_chunks": ("content_hash",),
    }
    for table, columns in hash_columns.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in columns:
                batch_op.add_column(sa.Column(column, sa.Text()))

    op.drop_index("ix_sources_owner_availability_title", table_name="sources")
    op.create_index(
        "ix_sources_owner_availability",
        "sources",
        ["owner_id", "availability_status"],
    )
    op.execute("DROP TRIGGER IF EXISTS trg_claims_required_citation_on_publish")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_claims_required_citation_on_published_insert"
    )
    with op.batch_alter_table("rubrics", schema=None) as batch_op:
        batch_op.drop_constraint("uq_rubrics_context_version", type_="unique")
        batch_op.create_unique_constraint(
            "uq_rubrics_body_version",
            ["owner_id", "body_hash", "capability", "version"],
        )
    with op.batch_alter_table("citations", schema=None) as batch_op:
        batch_op.drop_constraint("uq_citations_support", type_="unique")
        batch_op.create_unique_constraint(
            "uq_citations_support",
            ["claim_id", "source_id", "source_snapshot_id", "body_hash"],
        )

    governed_body_specs = (
        (
            "evidence_summary_bodies",
            "evidence_id",
            "evidence",
            True,
            (("summary", False),),
        ),
        (
            "rubric_bodies",
            "rubric_id",
            "rubrics",
            False,
            (
                ("task_context", False),
                ("role_context", True),
                ("level_context", True),
                ("provenance", False),
            ),
        ),
        (
            "rubric_dimension_bodies",
            "dimension_id",
            "rubric_dimensions",
            False,
            (("name", False), ("description", False), ("evaluation_guidance", False)),
        ),
        (
            "assessment_bodies",
            "assessment_id",
            "assessments",
            True,
            (
                ("task_ref", False),
                ("role_context", True),
                ("level_context", True),
                ("assumptions_json", False),
                ("source_refs_json", False),
                ("provenance_refs_json", False),
                ("facts_json", False),
                ("trade_offs_json", False),
                ("citations_json", False),
                ("ambiguities_json", False),
                ("feedback", False),
                ("cross_question_candidate", True),
                ("revision_invitation", True),
                ("warnings_json", False),
                ("limitation_labels_json", False),
            ),
        ),
        (
            "assessment_dimension_result_bodies",
            "result_id",
            "assessment_dimension_results",
            True,
            (("rationale", False), ("evidence_refs_json", False)),
        ),
        (
            "assessment_dispute_bodies",
            "dispute_id",
            "assessment_disputes",
            True,
            (("reason", False), ("resolution_note", True)),
        ),
        (
            "notebook_entry_bodies",
            "entry_id",
            "notebook_entries",
            True,
            (("markdown", False),),
        ),
        (
            "review_item_bodies",
            "review_item_id",
            "review_items",
            True,
            (("prompt", False), ("answer", True), ("context", True)),
        ),
        (
            "review_attempt_bodies",
            "attempt_id",
            "review_attempts",
            True,
            (
                ("response", False),
                ("feedback", True),
                ("correction", True),
                ("context_variation", True),
                ("context_result", True),
            ),
        ),
        (
            "hands_on_work_bodies",
            "work_id",
            "hands_on_work",
            True,
            (
                ("scenario_title", False),
                ("scenario_prompt", False),
                ("role", False),
                ("level", False),
                ("constraints_json", False),
                ("scenario_source", False),
            ),
        ),
        (
            "hands_on_artifact_bodies",
            "artifact_id",
            "hands_on_artifacts",
            True,
            (("cross_question_response", True),),
        ),
        (
            "hands_on_review_bodies",
            "review_id",
            "hands_on_reviews",
            True,
            (("required_limitation_label", False),),
        ),
        (
            "hands_on_cross_question_bodies",
            "question_id",
            "hands_on_cross_questions",
            True,
            (("question", False), ("target_gap", False)),
        ),
        (
            "source_bodies",
            "source_id",
            "sources",
            False,
            (("title", False), ("publisher", True), ("canonical_url", True)),
        ),
        (
            "citation_bodies",
            "citation_id",
            "citations",
            True,
            (("locator", False), ("note", True)),
        ),
        (
            "provider_request_bodies",
            "request_id",
            "provider_requests",
            False,
            (
                ("pid", True),
                ("pgid", True),
                ("process_identity", True),
                ("temp_path", True),
            ),
        ),
        (
            "schema_quarantine_bodies",
            "quarantine_id",
            "schema_quarantines",
            False,
            (("raw_output_ref", False), ("validation_errors_json", False)),
        ),
        (
            "search_document_bodies",
            "document_id",
            "search_documents",
            True,
            (("title", False), ("body", False), ("tags", False)),
        ),
    )
    for table, key, parent, goal_scoped, columns in governed_body_specs:
        child_columns = [
            sa.Column(key, sa.Text(), nullable=False),
            sa.Column("owner_id", sa.Text(), nullable=False),
        ]
        if goal_scoped:
            child_columns.append(sa.Column("goal_id", sa.Text(), nullable=False))
        child_columns.extend(
            sa.Column(
                name,
                sa.Integer() if name in {"pid", "pgid"} else sa.Text(),
                nullable=nullable,
            )
            for name, nullable in columns
        )
        parent_columns = [f"{parent}.id", f"{parent}.owner_id"]
        local_columns = [key, "owner_id"]
        if goal_scoped:
            parent_columns.append(f"{parent}.goal_id")
            local_columns.append("goal_id")
        op.create_table(
            table,
            *child_columns,
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
            sa.ForeignKeyConstraint(local_columns, parent_columns, ondelete="CASCADE"),
            sa.PrimaryKeyConstraint(key),
            *(
                (
                    sa.CheckConstraint(
                        "length(trim(markdown)) > 0", name="markdown_non_blank"
                    ),
                )
                if table == "notebook_entry_bodies"
                else (
                    sa.CheckConstraint(
                        "length(trim(prompt)) > 0", name="prompt_non_blank"
                    ),
                    sa.CheckConstraint(
                        "answer IS NULL OR length(trim(answer)) > 0",
                        name="answer_non_blank",
                    ),
                )
                if table == "review_item_bodies"
                else (
                    sa.CheckConstraint(
                        "length(trim(response)) > 0", name="response_non_blank"
                    ),
                )
                if table == "review_attempt_bodies"
                else (
                    sa.CheckConstraint(
                        "length(trim(title)) > 0", name="title_non_blank"
                    ),
                )
                if table == "source_bodies"
                else (
                    sa.CheckConstraint(
                        "length(trim(locator)) > 0", name="locator_non_blank"
                    ),
                )
                if table == "citation_bodies"
                else (
                    sa.CheckConstraint(
                        "json_valid(validation_errors_json)",
                        name="validation_errors_json_valid",
                    ),
                )
                if table == "schema_quarantine_bodies"
                else (
                    sa.CheckConstraint(
                        "length(trim(role)) > 0",
                        name="hands_on_work_bodies_role_non_blank",
                    ),
                )
                if table == "hands_on_work_bodies"
                else ()
            ),
            *tuple(
                sa.CheckConstraint(expression, name=name)
                for expression, name in {
                    "rubric_bodies": (
                        ("length(trim(task_context)) > 0", "task_context_non_blank"),
                        ("length(trim(provenance)) > 0", "provenance_non_blank"),
                    ),
                    "rubric_dimension_bodies": (
                        ("length(trim(name)) > 0", "name_non_blank"),
                    ),
                    "assessment_bodies": tuple(
                        (f"json_valid({column})", f"{column}_valid")
                        for column in (
                            "assumptions_json",
                            "source_refs_json",
                            "provenance_refs_json",
                            "facts_json",
                            "trade_offs_json",
                            "citations_json",
                            "ambiguities_json",
                            "warnings_json",
                            "limitation_labels_json",
                        )
                    ),
                    "assessment_dimension_result_bodies": (
                        ("json_valid(evidence_refs_json)", "evidence_refs_json_valid"),
                    ),
                    "assessment_dispute_bodies": (
                        ("length(trim(reason)) > 0", "reason_non_blank"),
                    ),
                    "hands_on_work_bodies": (
                        (
                            "length(trim(scenario_title)) > 0",
                            "hands_on_scenario_title_non_blank",
                        ),
                        (
                            "length(trim(scenario_prompt)) > 0",
                            "hands_on_scenario_prompt_non_blank",
                        ),
                        ("length(trim(level)) > 0", "hands_on_level_non_blank"),
                        (
                            "json_valid(constraints_json) AND json_type(constraints_json) = 'array'",
                            "hands_on_constraints_array",
                        ),
                        (
                            "length(trim(scenario_source)) > 0",
                            "hands_on_scenario_source_non_blank",
                        ),
                    ),
                    "hands_on_review_bodies": (
                        (
                            "length(trim(required_limitation_label)) > 0",
                            "hands_on_static_limitation_non_blank",
                        ),
                    ),
                    "hands_on_cross_question_bodies": (
                        ("length(trim(question)) > 0", "hands_on_question_non_blank"),
                        (
                            "length(trim(target_gap)) > 0",
                            "hands_on_target_gap_non_blank",
                        ),
                    ),
                }.get(table, ())
            ),
        )
    op.create_table(
        "claim_bodies",
        sa.Column("claim_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text()),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["claim_id", "owner_id"],
            ["claims.id", "claims.owner_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.CheckConstraint("length(trim(claim_text)) > 0", name="claim_text_non_blank"),
    )
    op.create_table(
        "goal_progress_memo_bodies",
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("coverage", sa.Text(), nullable=False),
        sa.Column("proficiency", sa.Text(), nullable=False),
        sa.Column("retention", sa.Text(), nullable=False),
        sa.Column("readiness", sa.Text(), nullable=False),
        sa.Column("explanation_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_progress_memos.goal_id", "goal_progress_memos.owner_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("goal_id"),
        sa.CheckConstraint(
            "coverage IN ('likely-known','partial','unverified','new')",
            name="coverage_valid",
        ),
        sa.CheckConstraint(
            "proficiency IN ('likely-known','partial','unverified','new')",
            name="proficiency_valid",
        ),
        sa.CheckConstraint(
            "retention IN ('likely-known','partial','unverified','new')",
            name="retention_valid",
        ),
        sa.CheckConstraint(
            "readiness IN ('likely-known','partial','unverified','new')",
            name="readiness_valid",
        ),
        sa.CheckConstraint(
            "json_valid(explanation_json)", name="explanation_json_valid"
        ),
    )
    op.create_table(
        "source_snapshot_bodies",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("version_label", sa.Text()),
        sa.Column("redacted_failure", sa.Text()),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "owner_id", "source_id"],
            [
                "source_snapshots.id",
                "source_snapshots.owner_id",
                "source_snapshots.source_id",
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.CheckConstraint(
            "length(trim(content_ref)) > 0", name="content_ref_non_blank"
        ),
    )
    rebuild_triggers = (
        "trg_overlay_entries_no_update",
        "trg_overlay_entries_no_delete",
        "trg_overlay_proposal_decisions_no_update",
        "trg_overlay_proposal_decisions_no_delete",
        "trg_learner_corrections_no_update",
        "trg_learner_corrections_no_delete",
        "trg_learner_corrections_linear_chain",
        "trg_progress_invalidate_assessment_insert",
        "trg_progress_invalidate_dimension_insert",
        "trg_progress_invalidate_assessment_update",
        "trg_progress_invalidate_correction",
        "trg_progress_invalidate_transfer",
        "trg_progress_invalidate_state_update",
        "trg_progress_invalidate_goal_graph",
        "trg_progress_invalidate_tombstone",
    )
    for trigger in rebuild_triggers:
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.create_table(
        "runner_confirmation_input_bodies",
        sa.Column("input_id", sa.Text(), nullable=False),
        sa.Column("resolved_content", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["input_id", "owner_id"],
            ["runner_confirmation_inputs.id", "runner_confirmation_inputs.owner_id"],
            name=op.f(
                "fk_runner_confirmation_input_bodies_input_id_runner_confirmation_inputs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_runner_confirmation_input_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint(
            "input_id", name=op.f("pk_runner_confirmation_input_bodies")
        ),
    )
    op.create_table(
        "runner_record_bodies",
        sa.Column("runner_id", sa.Text(), nullable=False),
        sa.Column("argv_json", sa.Text(), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("pgid", sa.Integer(), nullable=True),
        sa.Column("temp_path", sa.Text(), nullable=True),
        sa.Column("outcome_json", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(argv_json)",
            name=op.f("ck_runner_record_bodies_argv_json_valid"),
        ),
        sa.CheckConstraint(
            "outcome_json IS NULL OR json_valid(outcome_json)",
            name=op.f("ck_runner_record_bodies_outcome_json_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_runner_record_bodies_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["runner_id", "owner_id"],
            ["runner_records.id", "runner_records.owner_id"],
            name=op.f("fk_runner_record_bodies_runner_id_runner_records"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("runner_id", name=op.f("pk_runner_record_bodies")),
    )
    op.create_table(
        "runner_input_bodies",
        sa.Column("input_id", sa.Text(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["input_id", "owner_id"],
            ["runner_inputs.id", "runner_inputs.owner_id"],
            name=op.f("fk_runner_input_bodies_input_id_runner_inputs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_runner_input_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("input_id", name=op.f("pk_runner_input_bodies")),
    )
    op.create_table(
        "runner_output_chunk_bodies",
        sa.Column("chunk_id", sa.Text(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id", "owner_id"],
            ["runner_output_chunks.id", "runner_output_chunks.owner_id"],
            name=op.f("fk_runner_output_chunk_bodies_chunk_id_runner_output_chunks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_runner_output_chunk_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("chunk_id", name=op.f("pk_runner_output_chunk_bodies")),
    )
    op.create_table(
        "diagnostic_session_bodies",
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("setup_inputs_json", sa.Text(), nullable=False),
        sa.Column("untrusted_seed_text", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(setup_inputs_json) AND json_type(setup_inputs_json)='object'",
            name=op.f("ck_diagnostic_session_bodies_setup_inputs_json_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_diagnostic_session_bodies_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "owner_id"],
            ["diagnostic_sessions.id", "diagnostic_sessions.owner_id"],
            name=op.f("fk_diagnostic_session_bodies_session_id_diagnostic_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "session_id", name=op.f("pk_diagnostic_session_bodies")
        ),
    )
    op.create_table(
        "export_package_bodies",
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("package_json", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(package_json)",
            name=op.f("ck_export_package_bodies_package_json_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["operation_id", "owner_id"],
            ["export_operations.id", "export_operations.owner_id"],
            name=op.f("fk_export_package_bodies_operation_id_export_operations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_export_package_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("operation_id", name=op.f("pk_export_package_bodies")),
    )
    op.create_table(
        "generated_artifact_bodies",
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("body_ref", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id", "owner_id", "goal_id"],
            [
                "generated_artifacts.id",
                "generated_artifacts.owner_id",
                "generated_artifacts.goal_id",
            ],
            name=op.f("fk_generated_artifact_bodies_artifact_id_generated_artifacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_generated_artifact_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint(
            "artifact_id", name=op.f("pk_generated_artifact_bodies")
        ),
    )
    op.create_table(
        "import_record_bodies",
        sa.Column("import_id", sa.Text(), nullable=False),
        sa.Column("original_content", sa.LargeBinary(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_id", "owner_id"],
            ["import_records.id", "import_records.owner_id"],
            name=op.f("fk_import_record_bodies_import_id_import_records"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_import_record_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("import_id", name=op.f("pk_import_record_bodies")),
    )
    op.create_table(
        "job_bodies",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("diagnostic", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(payload_json)", name=op.f("ck_job_bodies_payload_json_valid")
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            name=op.f("fk_job_bodies_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_job_bodies_owner_id_owners")
        ),
        sa.PrimaryKeyConstraint("job_id", name=op.f("pk_job_bodies")),
    )
    op.create_table(
        "topic_conversation_turn_bodies",
        sa.Column("turn_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_topic_conversation_turn_bodies_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["turn_id", "owner_id", "goal_id"],
            [
                "topic_conversation_turns.id",
                "topic_conversation_turns.owner_id",
                "topic_conversation_turns.goal_id",
            ],
            name=op.f(
                "fk_topic_conversation_turn_bodies_turn_id_topic_conversation_turns"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "turn_id", name=op.f("pk_topic_conversation_turn_bodies")
        ),
    )
    op.create_table(
        "diagnostic_answer_bodies",
        sa.Column("answer_id", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["answer_id", "owner_id"],
            ["diagnostic_answers.id", "diagnostic_answers.owner_id"],
            name=op.f("fk_diagnostic_answer_bodies_answer_id_diagnostic_answers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_diagnostic_answer_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("answer_id", name=op.f("pk_diagnostic_answer_bodies")),
    )
    op.create_table(
        "diagnostic_preview_edit_bodies",
        sa.Column("edit_id", sa.Text(), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(value_json) AND json_type(value_json)='object'",
            name=op.f("ck_diagnostic_preview_edit_bodies_value_json_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["edit_id", "owner_id"],
            ["diagnostic_preview_edits.id", "diagnostic_preview_edits.owner_id"],
            name=op.f(
                "fk_diagnostic_preview_edit_bodies_edit_id_diagnostic_preview_edits"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_diagnostic_preview_edit_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint(
            "edit_id", name=op.f("pk_diagnostic_preview_edit_bodies")
        ),
    )
    op.create_table(
        "import_statement_bodies",
        sa.Column("statement_id", sa.Text(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_import_statement_bodies_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["statement_id", "owner_id"],
            ["import_statements.id", "import_statements.owner_id"],
            name=op.f("fk_import_statement_bodies_statement_id_import_statements"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "statement_id", name=op.f("pk_import_statement_bodies")
        ),
    )
    op.create_table(
        "job_attempt_bodies",
        sa.Column("attempt_id", sa.Text(), nullable=False),
        sa.Column("process_identity", sa.Text(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("pgid", sa.Integer(), nullable=True),
        sa.Column("temp_path", sa.Text(), nullable=True),
        sa.Column("diagnostic", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id", "owner_id"],
            ["job_attempts.id", "job_attempts.owner_id"],
            name=op.f("fk_job_attempt_bodies_attempt_id_job_attempts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_job_attempt_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("attempt_id", name=op.f("pk_job_attempt_bodies")),
    )
    op.create_table(
        "job_result_bodies",
        sa.Column("result_id", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.Text(), nullable=False),
        sa.Column("diagnostic_ref", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(warnings_json)",
            name=op.f("ck_job_result_bodies_warnings_json_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_job_result_bodies_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["result_id", "owner_id"],
            ["job_results.id", "job_results.owner_id"],
            name=op.f("fk_job_result_bodies_result_id_job_results"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("result_id", name=op.f("pk_job_result_bodies")),
    )
    op.create_table(
        "import_statement_decision_bodies",
        sa.Column("decision_id", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["decision_id", "owner_id"],
            ["import_statement_decisions.id", "import_statement_decisions.owner_id"],
            name=op.f(
                "fk_import_statement_decision_bodies_decision_id_import_statement_decisions"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_import_statement_decision_bodies_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint(
            "decision_id", name=op.f("pk_import_statement_decision_bodies")
        ),
    )
    op.create_table(
        "interview_run_bodies",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("hint_text", sa.Text(), nullable=True),
        sa.Column("draft", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_interview_run_bodies_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "owner_id", "goal_id"],
            ["interview_runs.id", "interview_runs.owner_id", "interview_runs.goal_id"],
            name=op.f("fk_interview_run_bodies_run_id_interview_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_interview_run_bodies")),
    )
    op.create_table(
        "interview_turn_bodies",
        sa.Column("turn_id", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_interview_turn_bodies_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["turn_id", "owner_id"],
            ["interview_turns.id", "interview_turns.owner_id"],
            name=op.f("fk_interview_turn_bodies_turn_id_interview_turns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("turn_id", name=op.f("pk_interview_turn_bodies")),
    )
    op.create_table(
        "interview_turn_result_bodies",
        sa.Column("result_id", sa.Text(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("cross_question_candidate", sa.Text(), nullable=True),
        sa.Column("facts_json", sa.Text(), nullable=False),
        sa.Column("trade_offs_json", sa.Text(), nullable=False),
        sa.Column("dimensions_json", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "json_valid(facts_json) AND json_valid(trade_offs_json) AND json_valid(dimensions_json)",
            name=op.f("ck_interview_turn_result_bodies_result_json_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_interview_turn_result_bodies_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["result_id", "owner_id"],
            ["interview_turn_results.id", "interview_turn_results.owner_id"],
            name=op.f(
                "fk_interview_turn_result_bodies_result_id_interview_turn_results"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "result_id", name=op.f("pk_interview_turn_result_bodies")
        ),
    )
    idempotency_tables = (
        "profiles_goals_idempotency",
        "roadmap_idempotency",
        "diagnostics_idempotency",
        "imports_idempotency",
        "interview_idempotency",
        "notebook_review_idempotency",
        "evidence_evaluation_idempotency",
        "learning_content_idempotency",
    )
    for parent in idempotency_tables:
        op.add_column(parent, sa.Column("response_hash", sa.Text()))
        op.create_table(
            f"{parent}_bodies",
            sa.Column("idempotency_id", sa.Text(), nullable=False),
            sa.Column("owner_id", sa.Text(), nullable=False),
            sa.Column("response_json", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
            sa.ForeignKeyConstraint(
                ["idempotency_id"], [f"{parent}.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("idempotency_id"),
            sa.CheckConstraint("json_valid(response_json)", name="response_json_valid"),
        )
        op.execute(
            f"INSERT INTO {parent}_bodies (idempotency_id,owner_id,response_json) "
            f"SELECT id,owner_id,response_json FROM {parent}"
        )

    op.add_column("merge_items", sa.Column("body_hash", sa.Text()))
    op.create_table(
        "merge_item_bodies",
        sa.Column("item_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.Column("resolution_explanation", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["item_id", "owner_id", "goal_id"],
            ["merge_items.id", "merge_items.owner_id", "merge_items.goal_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("item_id"),
        sa.CheckConstraint("json_valid(payload_json)", name="payload_json_valid"),
    )
    op.execute(
        "INSERT INTO merge_item_bodies (item_id,owner_id,goal_id,title,summary,impact,resolution_explanation,payload_json) "
        "SELECT id,owner_id,goal_id,title,summary,impact,resolution_explanation,payload_json FROM merge_items"
    )
    op.create_table(
        "canonical_merge_followup_bodies",
        sa.Column("followup_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["followup_id", "owner_id", "goal_id"],
            [
                "canonical_merge_followups.id",
                "canonical_merge_followups.owner_id",
                "canonical_merge_followups.goal_id",
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("followup_id"),
        sa.CheckConstraint("json_valid(payload_json)", name="payload_json_valid"),
    )
    op.execute(
        "INSERT INTO canonical_merge_followup_bodies (followup_id,owner_id,goal_id,payload_json) "
        "SELECT id,owner_id,goal_id,payload_json FROM canonical_merge_followups"
    )

    op.add_column("interview_bundles", sa.Column("body_hash", sa.Text()))
    op.add_column("interview_bundle_items", sa.Column("body_hash", sa.Text()))
    op.create_table(
        "interview_bundle_bodies",
        sa.Column("bundle_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("generic_role", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["bundle_id", "owner_id"],
            ["interview_bundles.id", "interview_bundles.owner_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("bundle_id"),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_non_blank"),
        sa.CheckConstraint(
            "length(trim(generic_role)) > 0", name="generic_role_non_blank"
        ),
        sa.CheckConstraint("length(trim(origin)) > 0", name="origin_non_blank"),
    )
    op.execute(
        "INSERT INTO interview_bundle_bodies (bundle_id,owner_id,name,generic_role,origin) "
        "SELECT id,owner_id,name,generic_role,origin FROM interview_bundles"
    )
    op.create_table(
        "interview_bundle_item_bodies",
        sa.Column("item_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("question", sa.Text()),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(
            ["item_id", "owner_id"],
            ["interview_bundle_items.id", "interview_bundle_items.owner_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("item_id"),
        sa.CheckConstraint(
            "question IS NULL OR length(trim(question)) > 0", name="question_non_blank"
        ),
    )
    op.execute(
        "INSERT INTO interview_bundle_item_bodies (item_id,owner_id,question) "
        "SELECT id,owner_id,question FROM interview_bundle_items"
    )

    bind = op.get_bind()
    for parent in idempotency_tables:
        for row in bind.execute(sa.text(f"SELECT id,response_json FROM {parent}")):
            digest = hashlib.sha256(
                json.dumps(
                    row.response_json, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            bind.execute(
                sa.text(f"UPDATE {parent} SET response_hash=:digest WHERE id=:id"),
                {"digest": digest, "id": row.id},
            )
    for row in bind.execute(
        sa.text(
            "SELECT id,title,summary,impact,resolution_explanation,payload_json FROM merge_items"
        )
    ).mappings():
        body = {
            key: row[key]
            for key in (
                "title",
                "summary",
                "impact",
                "resolution_explanation",
                "payload_json",
            )
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        bind.execute(
            sa.text("UPDATE merge_items SET body_hash=:digest WHERE id=:id"),
            {"digest": digest, "id": row["id"]},
        )
    for table, key, columns in (
        ("interview_bundles", "id", ("name", "generic_role", "origin")),
        ("interview_bundle_items", "id", ("question",)),
    ):
        for row in bind.execute(
            sa.text(f"SELECT {key},{','.join(columns)} FROM {table}")
        ).mappings():
            value = (
                {column: row[column] for column in columns}
                if len(columns) > 1
                else row[columns[0]]
            )
            digest = hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            bind.execute(
                sa.text(f"UPDATE {table} SET body_hash=:digest WHERE {key}=:id"),
                {"digest": digest, "id": row[key]},
            )
    op.execute("DROP TRIGGER IF EXISTS trg_job_events_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_job_attempts_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_job_results_immutable_delete")
    for trigger in (
        "trg_interview_turns_mock_feedback_withheld",
        "trg_interview_turn_results_mock_terminal_visibility",
        "trg_interview_turn_results_terminal_visibility",
        "trg_interview_turns_immutable_update",
        "trg_interview_turns_immutable_delete",
        "trg_interview_turn_results_immutable_update",
        "trg_interview_turn_results_immutable_delete",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    # Backfill every child body before dropping its former header columns.
    backfills = (
        (
            "evidence_summary_bodies",
            "evidence_id,owner_id,goal_id,summary",
            "SELECT id,owner_id,goal_id,summary FROM evidence",
        ),
        (
            "rubric_bodies",
            "rubric_id,owner_id,task_context,role_context,level_context,provenance",
            "SELECT id,owner_id,task_context,role_context,level_context,provenance FROM rubrics",
        ),
        (
            "rubric_dimension_bodies",
            "dimension_id,owner_id,name,description,evaluation_guidance",
            "SELECT id,owner_id,name,description,evaluation_guidance FROM rubric_dimensions",
        ),
        (
            "assessment_bodies",
            "assessment_id,owner_id,goal_id,task_ref,role_context,level_context,assumptions_json,source_refs_json,provenance_refs_json,facts_json,trade_offs_json,citations_json,ambiguities_json,feedback,cross_question_candidate,revision_invitation,warnings_json,limitation_labels_json",
            "SELECT id,owner_id,goal_id,task_ref,role_context,level_context,assumptions_json,source_refs_json,provenance_refs_json,facts_json,trade_offs_json,citations_json,ambiguities_json,feedback,cross_question_candidate,revision_invitation,warnings_json,limitation_labels_json FROM assessments",
        ),
        (
            "assessment_dimension_result_bodies",
            "result_id,owner_id,goal_id,rationale,evidence_refs_json",
            "SELECT id,owner_id,goal_id,rationale,evidence_refs_json FROM assessment_dimension_results",
        ),
        (
            "assessment_dispute_bodies",
            "dispute_id,owner_id,goal_id,reason,resolution_note",
            "SELECT id,owner_id,goal_id,reason,resolution_note FROM assessment_disputes",
        ),
        (
            "goal_progress_memo_bodies",
            "goal_id,owner_id,coverage,proficiency,retention,readiness,explanation_json",
            "SELECT goal_id,owner_id,coverage,proficiency,retention,readiness,explanation_json FROM goal_progress_memos",
        ),
        (
            "notebook_entry_bodies",
            "entry_id,owner_id,goal_id,markdown",
            "SELECT id,owner_id,goal_id,markdown FROM notebook_entries",
        ),
        (
            "review_item_bodies",
            "review_item_id,owner_id,goal_id,prompt,answer,context",
            "SELECT id,owner_id,goal_id,prompt,answer,context FROM review_items",
        ),
        (
            "review_attempt_bodies",
            "attempt_id,owner_id,goal_id,response,feedback,correction,context_variation,context_result",
            "SELECT id,owner_id,goal_id,response,feedback,correction,context_variation,context_result FROM review_attempts",
        ),
        (
            "hands_on_work_bodies",
            "work_id,owner_id,goal_id,scenario_title,scenario_prompt,role,level,constraints_json,scenario_source",
            "SELECT id,owner_id,goal_id,scenario_title,scenario_prompt,role,level,constraints_json,scenario_source FROM hands_on_work",
        ),
        (
            "hands_on_artifact_bodies",
            "artifact_id,owner_id,goal_id,cross_question_response",
            "SELECT id,owner_id,goal_id,cross_question_response FROM hands_on_artifacts",
        ),
        (
            "hands_on_review_bodies",
            "review_id,owner_id,goal_id,required_limitation_label",
            "SELECT id,owner_id,goal_id,required_limitation_label FROM hands_on_reviews",
        ),
        (
            "hands_on_cross_question_bodies",
            "question_id,owner_id,goal_id,question,target_gap",
            "SELECT id,owner_id,goal_id,question,target_gap FROM hands_on_cross_questions",
        ),
        (
            "source_bodies",
            "source_id,owner_id,title,publisher,canonical_url",
            "SELECT id,owner_id,title,publisher,canonical_url FROM sources",
        ),
        (
            "source_snapshot_bodies",
            "snapshot_id,owner_id,source_id,content_ref,version_label,redacted_failure",
            "SELECT id,owner_id,source_id,content_ref,version_label,redacted_failure FROM source_snapshots",
        ),
        (
            "claim_bodies",
            "claim_id,owner_id,goal_id,claim_text",
            "SELECT id,owner_id,goal_id,claim_text FROM claims",
        ),
        (
            "citation_bodies",
            "citation_id,owner_id,goal_id,locator,note",
            "SELECT id,owner_id,goal_id,locator,note FROM citations",
        ),
        (
            "provider_request_bodies",
            "request_id,owner_id,pid,pgid,process_identity,temp_path",
            "SELECT id,owner_id,pid,pgid,process_identity,temp_path FROM provider_requests",
        ),
        (
            "schema_quarantine_bodies",
            "quarantine_id,owner_id,raw_output_ref,validation_errors_json",
            "SELECT id,owner_id,raw_output_ref,validation_errors_json FROM schema_quarantines",
        ),
        (
            "search_document_bodies",
            "document_id,owner_id,goal_id,title,body,tags",
            "SELECT id,owner_id,goal_id,title,body,tags FROM search_documents",
        ),
        (
            "learner_profile_bodies",
            "owner_id,experience,strengths,weaknesses",
            "SELECT owner_id,experience,strengths,weaknesses FROM learner_profiles",
        ),
        (
            "goal_workspace_bodies",
            "goal_id,owner_id,name,subject,role,resume_position",
            "SELECT id,owner_id,name,subject,role,resume_position FROM goal_workspaces",
        ),
        (
            "overlay_entry_bodies",
            "entry_id,owner_id,goal_id,value_json,reason",
            "SELECT id,owner_id,goal_id,value_json,reason FROM overlay_entries",
        ),
        (
            "overlay_proposal_bodies",
            "proposal_id,owner_id,goal_id,payload_json,state_reason",
            "SELECT id,owner_id,goal_id,payload_json,state_reason FROM overlay_proposals",
        ),
        (
            "overlay_proposal_decision_bodies",
            "decision_id,owner_id,goal_id,reason",
            "SELECT id,owner_id,goal_id,reason FROM overlay_proposal_decisions",
        ),
        (
            "learning_state_bodies",
            "state_id,owner_id,goal_id,explanation",
            "SELECT id,owner_id,goal_id,explanation FROM learning_states",
        ),
        (
            "learner_correction_bodies",
            "correction_id,owner_id,goal_id,value,reason",
            "SELECT id,owner_id,goal_id,value,reason FROM learner_corrections",
        ),
        (
            "transferred_evidence_ref_bodies",
            "transfer_id,owner_id,goal_id,rationale",
            "SELECT id,owner_id,goal_id,rationale FROM transferred_evidence_refs",
        ),
        (
            "diagnostic_session_bodies",
            "session_id,owner_id,setup_inputs_json,untrusted_seed_text",
            "SELECT id,owner_id,setup_inputs_json,untrusted_seed_text FROM diagnostic_sessions",
        ),
        (
            "diagnostic_answer_bodies",
            "answer_id,owner_id,answer",
            "SELECT id,owner_id,answer FROM diagnostic_answers",
        ),
        (
            "diagnostic_preview_edit_bodies",
            "edit_id,owner_id,value_json,reason",
            "SELECT id,owner_id,value_json,reason FROM diagnostic_preview_edits",
        ),
        (
            "import_record_bodies",
            "import_id,owner_id,original_content",
            "SELECT id,owner_id,original_content FROM import_records",
        ),
        (
            "import_statement_bodies",
            "statement_id,owner_id,original_text,normalized_text,corrected_text",
            "SELECT id,owner_id,original_text,normalized_text,corrected_text FROM import_statements",
        ),
        (
            "import_statement_decision_bodies",
            "decision_id,owner_id,value",
            "SELECT id,owner_id,value FROM import_statement_decisions",
        ),
        (
            "generated_artifact_bodies",
            "artifact_id,owner_id,goal_id,body_ref",
            "SELECT id,owner_id,goal_id,body_ref FROM generated_artifacts WHERE body_ref IS NOT NULL",
        ),
        (
            "topic_conversation_turn_bodies",
            "turn_id,owner_id,goal_id,body",
            "SELECT id,owner_id,goal_id,body FROM topic_conversation_turns",
        ),
        (
            "interview_run_bodies",
            "run_id,owner_id,goal_id,question,hint_text,draft",
            "SELECT id,owner_id,goal_id,question,hint_text,draft FROM interview_runs",
        ),
        (
            "interview_turn_bodies",
            "turn_id,owner_id,body",
            "SELECT id,owner_id,body FROM interview_turns",
        ),
        (
            "interview_turn_result_bodies",
            "result_id,owner_id,feedback,cross_question_candidate,facts_json,trade_offs_json,dimensions_json",
            "SELECT id,owner_id,feedback,cross_question_candidate,facts,trade_offs,dimensions FROM interview_turn_results",
        ),
        (
            "runner_confirmation_input_bodies",
            "input_id,owner_id,resolved_content",
            "SELECT id,owner_id,resolved_content FROM runner_confirmation_inputs",
        ),
        (
            "runner_record_bodies",
            "runner_id,owner_id,argv_json,pid,pgid,temp_path,outcome_json",
            "SELECT id,owner_id,argv_json,pid,pgid,temp_path,outcome_json FROM runner_records",
        ),
        (
            "runner_input_bodies",
            "input_id,owner_id,content_ref",
            "SELECT id,owner_id,content_ref FROM runner_inputs",
        ),
        (
            "runner_output_chunk_bodies",
            "chunk_id,owner_id,content_ref",
            "SELECT id,owner_id,content_ref FROM runner_output_chunks",
        ),
        (
            "job_bodies",
            "job_id,owner_id,payload_json,diagnostic",
            "SELECT id,owner_id,payload_json,diagnostic FROM jobs",
        ),
        (
            "job_attempt_bodies",
            "attempt_id,owner_id,process_identity,pid,pgid,temp_path,diagnostic",
            "SELECT id,owner_id,process_identity,pid,pgid,temp_path,diagnostic FROM job_attempts",
        ),
        (
            "job_result_bodies",
            "result_id,owner_id,warnings_json,diagnostic_ref",
            "SELECT id,owner_id,warnings_json,diagnostic_ref FROM job_results",
        ),
        (
            "export_package_bodies",
            "operation_id,owner_id,package_json",
            "SELECT id,owner_id,package_json FROM export_operations WHERE package_json IS NOT NULL",
        ),
    )
    for table, columns, query in backfills:
        op.execute(f"INSERT INTO {table} ({columns}) {query}")
    bind = op.get_bind()
    digest_specs = (
        ("evidence", "id", "summary_hash", ("summary",)),
        (
            "rubrics",
            "id",
            "body_hash",
            ("task_context", "role_context", "level_context", "provenance"),
        ),
        (
            "rubric_dimensions",
            "id",
            "body_hash",
            ("name", "description", "evaluation_guidance"),
        ),
        (
            "assessments",
            "id",
            "body_hash",
            (
                "task_ref",
                "role_context",
                "level_context",
                "assumptions_json",
                "source_refs_json",
                "provenance_refs_json",
                "facts_json",
                "trade_offs_json",
                "citations_json",
                "ambiguities_json",
                "feedback",
                "cross_question_candidate",
                "revision_invitation",
                "warnings_json",
                "limitation_labels_json",
            ),
        ),
        (
            "assessment_dimension_results",
            "id",
            "body_hash",
            ("rationale", "evidence_refs_json"),
        ),
        ("assessment_disputes", "id", "body_hash", ("reason", "resolution_note")),
        (
            "goal_progress_memos",
            "goal_id",
            "body_hash",
            ("coverage", "proficiency", "retention", "readiness", "explanation_json"),
        ),
        ("notebook_entries", "id", "body_hash", ("markdown",)),
        ("review_items", "id", "body_hash", ("prompt", "answer", "context")),
        (
            "review_attempts",
            "id",
            "body_hash",
            (
                "response",
                "feedback",
                "correction",
                "context_variation",
                "context_result",
            ),
        ),
        (
            "hands_on_work",
            "id",
            "body_hash",
            (
                "scenario_title",
                "scenario_prompt",
                "role",
                "level",
                "constraints_json",
                "scenario_source",
            ),
        ),
        ("hands_on_artifacts", "id", "body_hash", ("cross_question_response",)),
        ("hands_on_reviews", "id", "body_hash", ("required_limitation_label",)),
        ("hands_on_cross_questions", "id", "body_hash", ("question", "target_gap")),
        ("sources", "id", "body_hash", ("title", "publisher", "canonical_url")),
        ("claims", "id", "claim_hash", ("claim_text",)),
        ("citations", "id", "body_hash", ("locator", "note")),
        (
            "provider_requests",
            "id",
            "body_hash",
            ("pid", "pgid", "process_identity", "temp_path"),
        ),
        (
            "schema_quarantines",
            "id",
            "body_hash",
            ("raw_output_ref", "validation_errors_json"),
        ),
        ("search_documents", "id", "body_hash", ("title", "body", "tags")),
        (
            "learner_profiles",
            "owner_id",
            "body_hash",
            ("experience", "strengths", "weaknesses"),
        ),
        (
            "goal_workspaces",
            "id",
            "body_hash",
            ("name", "subject", "role", "resume_position"),
        ),
        ("overlay_proposal_decisions", "id", "body_hash", ("reason",)),
        ("learning_states", "id", "body_hash", ("explanation",)),
        ("learner_corrections", "id", "body_hash", ("value", "reason")),
        ("transferred_evidence_refs", "id", "body_hash", ("rationale",)),
        ("diagnostic_sessions", "id", "setup_inputs_hash", ("setup_inputs_json",)),
        ("diagnostic_sessions", "id", "untrusted_seed_hash", ("untrusted_seed_text",)),
        ("diagnostic_answers", "id", "answer_hash", ("answer",)),
        ("diagnostic_preview_edits", "id", "body_hash", ("value_json", "reason")),
        ("import_statements", "id", "corrected_hash", ("corrected_text",)),
        ("import_statement_decisions", "id", "value_hash", ("value",)),
        ("interview_runs", "id", "body_hash", ("question", "hint_text", "draft")),
        ("interview_turns", "id", "body_hash", ("body",)),
        (
            "interview_turn_results",
            "id",
            "body_hash",
            (
                "feedback",
                "cross_question_candidate",
                "facts",
                "trade_offs",
                "dimensions",
            ),
        ),
        ("topic_conversation_turns", "id", "body_hash", ("body",)),
        ("runner_output_chunks", "id", "content_hash", ("content_ref",)),
    )
    for table, key, target, sources in digest_specs:
        rows = bind.execute(sa.text(f"SELECT {key},{','.join(sources)} FROM {table}"))
        for row in rows.mappings():
            values = [row[source] for source in sources]
            if all(value is None for value in values) and target in {
                "untrusted_seed_hash",
                "corrected_hash",
                "value_hash",
            }:
                continue
            canonical = "\x1f".join(
                "" if value is None else str(value) for value in values
            )
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            bind.execute(
                sa.text(f"UPDATE {table} SET {target}=:digest WHERE {key}=:key"),
                {"digest": digest, "key": row[key]},
            )
    for hash_spec in (
        "evidence summary_hash",
        "rubrics body_hash",
        "rubric_dimensions body_hash",
        "assessments body_hash",
        "assessment_dimension_results body_hash",
        "assessment_disputes body_hash",
        "goal_progress_memos body_hash",
        "notebook_entries body_hash",
        "review_items body_hash",
        "review_attempts body_hash",
        "hands_on_work body_hash",
        "hands_on_artifacts body_hash",
        "hands_on_reviews body_hash",
        "hands_on_cross_questions body_hash",
        "sources body_hash",
        "claims claim_hash",
        "citations body_hash",
        "provider_requests body_hash",
        "schema_quarantines body_hash",
        "search_documents body_hash",
    ):
        table, column = hash_spec.split()
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(column, existing_type=sa.Text(), nullable=False)

    tombstoned_refs = bind.execute(
        sa.text("""
        SELECT g.owner_id,g.id goal_id,g.updated_at,'source-snapshot' kind,b.content_ref path_ref
        FROM goal_workspaces g JOIN citations c ON c.owner_id=g.owner_id AND c.goal_id=g.id
        JOIN source_snapshot_bodies b ON b.owner_id=c.owner_id AND b.snapshot_id=c.source_snapshot_id
        WHERE g.status='tombstoned' AND NOT EXISTS (
          SELECT 1 FROM citations active_c JOIN goal_workspaces active_g
            ON active_g.owner_id=active_c.owner_id AND active_g.id=active_c.goal_id
          WHERE active_c.owner_id=c.owner_id AND active_c.source_snapshot_id=c.source_snapshot_id
            AND active_g.status!='tombstoned')
        UNION ALL
        SELECT g.owner_id,g.id,g.updated_at,'provider-quarantine',b.raw_output_ref
        FROM goal_workspaces g JOIN provider_requests p ON p.owner_id=g.owner_id AND p.goal_id=g.id
        JOIN schema_quarantines q ON q.owner_id=p.owner_id AND q.provider_request_id=p.id
        JOIN schema_quarantine_bodies b ON b.owner_id=q.owner_id AND b.quarantine_id=q.id
        WHERE g.status='tombstoned'
        UNION ALL
        SELECT g.owner_id,g.id,g.updated_at,'runner-workspace',b.temp_path
        FROM goal_workspaces g JOIN runner_records r ON r.owner_id=g.owner_id AND r.goal_id=g.id
        JOIN runner_record_bodies b ON b.owner_id=r.owner_id AND b.runner_id=r.id
        WHERE g.status='tombstoned' AND b.temp_path IS NOT NULL
    """)
    ).mappings()
    for ref in tombstoned_refs:
        path_ref = ref["path_ref"]
        if not path_ref:
            continue
        canonical = json.dumps(path_ref, sort_keys=True, separators=(",", ":"))
        identity = (
            f"{ref['owner_id']}\x1f{ref['goal_id']}\x1f{ref['kind']}\x1f{path_ref}"
        )
        bind.execute(
            sa.text("""
            INSERT OR IGNORE INTO file_cleanup_intents
              (id,owner_id,goal_id,kind,path_ref,path_hash,status,failure_classification,attempts,created_at,updated_at,completed_at)
            VALUES (:id,:owner_id,:goal_id,:kind,:path_ref,:path_hash,'pending',NULL,0,:at,:at,NULL)
        """),
            {
                "id": hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32],
                "owner_id": ref["owner_id"],
                "goal_id": ref["goal_id"],
                "kind": ref["kind"],
                "path_ref": path_ref,
                "path_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                "at": ref["updated_at"],
            },
        )
    bind.execute(
        sa.text("""
        DELETE FROM source_snapshot_bodies WHERE snapshot_id IN (
          SELECT c.source_snapshot_id FROM citations c JOIN goal_workspaces g
            ON g.owner_id=c.owner_id AND g.id=c.goal_id
          WHERE g.status='tombstoned' AND c.source_snapshot_id IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM citations active_c JOIN goal_workspaces active_g
              ON active_g.owner_id=active_c.owner_id AND active_g.id=active_c.goal_id
              WHERE active_c.owner_id=c.owner_id AND active_c.source_snapshot_id=c.source_snapshot_id
                AND active_g.status!='tombstoned'))
    """)
    )
    tombstoned_goal_body_tables = (
        "merge_item_bodies",
        "canonical_merge_followup_bodies",
        "goal_workspace_bodies",
        "evidence_summary_bodies",
        "assessment_bodies",
        "assessment_dimension_result_bodies",
        "assessment_dispute_bodies",
        "goal_progress_memo_bodies",
        "notebook_entry_bodies",
        "review_item_bodies",
        "review_attempt_bodies",
        "hands_on_work_bodies",
        "hands_on_artifact_bodies",
        "hands_on_review_bodies",
        "hands_on_cross_question_bodies",
        "claim_bodies",
        "citation_bodies",
        "search_document_bodies",
        "overlay_entry_bodies",
        "overlay_proposal_bodies",
        "overlay_proposal_decision_bodies",
        "learning_state_bodies",
        "learner_correction_bodies",
        "transferred_evidence_ref_bodies",
        "generated_artifact_bodies",
        "topic_conversation_turn_bodies",
        "interview_run_bodies",
    )
    for table in tombstoned_goal_body_tables:
        bind.execute(
            sa.text(
                f"DELETE FROM {table} WHERE (owner_id,goal_id) IN "
                "(SELECT owner_id,id FROM goal_workspaces WHERE status='tombstoned')"
            )
        )
    bind.execute(
        sa.text(
            "DELETE FROM evidence_payloads WHERE (owner_id,goal_id) IN "
            "(SELECT owner_id,id FROM goal_workspaces WHERE status='tombstoned')"
        )
    )
    indirect_tombstone_deletes = (
        "DELETE FROM interview_bundle_item_bodies WHERE item_id IN (SELECT i.id FROM interview_bundle_items i JOIN interview_bundles b ON b.id=i.bundle_id AND b.owner_id=i.owner_id JOIN goal_workspaces g ON g.id=b.goal_id AND g.owner_id=b.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM interview_bundle_bodies WHERE bundle_id IN (SELECT b.id FROM interview_bundles b JOIN goal_workspaces g ON g.id=b.goal_id AND g.owner_id=b.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM import_statement_decision_bodies WHERE decision_id IN (SELECT d.id FROM import_statement_decisions d JOIN import_statements s ON s.id=d.statement_id JOIN import_records i ON i.id=s.import_id JOIN goal_workspaces g ON g.id=i.goal_id AND g.owner_id=i.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM import_statement_bodies WHERE statement_id IN (SELECT s.id FROM import_statements s JOIN import_records i ON i.id=s.import_id JOIN goal_workspaces g ON g.id=i.goal_id AND g.owner_id=i.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM import_record_bodies WHERE import_id IN (SELECT i.id FROM import_records i JOIN goal_workspaces g ON g.id=i.goal_id AND g.owner_id=i.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM interview_turn_bodies WHERE turn_id IN (SELECT t.id FROM interview_turns t JOIN interview_runs r ON r.id=t.run_id JOIN goal_workspaces g ON g.id=r.goal_id AND g.owner_id=r.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM interview_turn_result_bodies WHERE result_id IN (SELECT x.id FROM interview_turn_results x JOIN interview_runs r ON r.id=x.run_id JOIN goal_workspaces g ON g.id=r.goal_id AND g.owner_id=r.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM provider_request_bodies WHERE request_id IN (SELECT p.id FROM provider_requests p JOIN goal_workspaces g ON g.id=p.goal_id AND g.owner_id=p.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM schema_quarantine_bodies WHERE quarantine_id IN (SELECT q.id FROM schema_quarantines q JOIN provider_requests p ON p.id=q.provider_request_id AND p.owner_id=q.owner_id JOIN goal_workspaces g ON g.id=p.goal_id AND g.owner_id=p.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM job_bodies WHERE job_id IN (SELECT j.id FROM jobs j JOIN goal_workspaces g ON g.id=j.goal_id AND g.owner_id=j.owner_id WHERE g.status='tombstoned')",
        "DELETE FROM runner_record_bodies WHERE runner_id IN (SELECT r.id FROM runner_records r JOIN goal_workspaces g ON g.id=r.goal_id AND g.owner_id=r.owner_id WHERE g.status='tombstoned')",
    )
    for statement in indirect_tombstone_deletes:
        bind.execute(sa.text(statement))
    op.add_column("runner_records", sa.Column("limit_classification", sa.Text()))
    op.add_column("runner_records", sa.Column("argv_hash", sa.Text()))
    op.add_column("runner_records", sa.Column("outcome_hash", sa.Text()))
    op.add_column("runner_records", sa.Column("temp_path_hash", sa.Text()))
    op.add_column("runner_records", sa.Column("cleanup_classification", sa.Text()))

    runner_records = bind.execute(
        sa.text(
            "SELECT id,argv_json,temp_path,outcome_json,cleanup_diagnostic FROM runner_records"
        )
    )
    for row in runner_records.mappings():

        def payload_hash(value: object) -> str | None:
            if value is None:
                return None
            encoded = json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            return hashlib.sha256(encoded).hexdigest()

        argv = json.loads(row["argv_json"])
        outcome = json.loads(row["outcome_json"]) if row["outcome_json"] else None
        bind.execute(
            sa.text(
                "UPDATE runner_records SET argv_hash=:argv_hash,outcome_hash=:outcome_hash,temp_path_hash=:temp_path_hash,cleanup_classification=:cleanup_classification WHERE id=:id"
            ),
            {
                "id": row["id"],
                "argv_hash": payload_hash(argv),
                "outcome_hash": payload_hash(outcome),
                "temp_path_hash": payload_hash(row["temp_path"]),
                "cleanup_classification": row["cleanup_diagnostic"],
            },
        )
    with op.batch_alter_table("export_operations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("filename", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("package_hash", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("package_expires_at", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("metadata_expires_at", sa.Text(), nullable=True))
        batch_op.drop_constraint(
            batch_op.f("ck_export_operations_package_json_valid"), type_="check"
        )
        batch_op.drop_constraint(
            batch_op.f("ck_export_operations_status_valid"), type_="check"
        )
        batch_op.create_check_constraint(
            batch_op.f("ck_export_operations_status_valid"),
            "status IN ('queued','running','complete','failed','expired')",
        )
        batch_op.drop_column("package_json")

    with op.batch_alter_table("diagnostic_sessions", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("ck_diagnostic_sessions_state_valid"), type_="check"
        )
        batch_op.create_check_constraint(
            batch_op.f("ck_diagnostic_sessions_state_valid"),
            "state IN ('not-started','in-progress','paused','resumed','skipped','roadmap-preview','failed','confirmed','expired')",
        )

    op.execute("DROP TABLE search_fts")
    for trigger in (
        "trg_rubrics_no_update",
        "trg_rubrics_no_delete",
        "trg_rubrics_no_insert_replace",
        "trg_rubric_dimensions_no_update",
        "trg_rubric_dimensions_no_delete",
        "trg_rubric_dimensions_no_insert_replace",
        "trg_assessments_lifecycle_update",
        "trg_assessments_no_delete",
        "trg_assessments_no_insert_replace",
        "trg_assessments_linear_chain_insert",
        "trg_assessment_dimension_results_no_update",
        "trg_assessment_dimension_results_no_delete",
        "trg_assessment_dimension_results_no_insert_replace",
        "trg_assessment_disputes_no_update",
        "trg_assessment_disputes_no_delete",
        "trg_assessment_disputes_no_insert_replace",
        "trg_review_attempts_no_update",
        "trg_review_attempts_no_delete",
        "trg_review_attempts_no_insert_replace",
        "hands_on_work_immutable_update",
        "hands_on_work_immutable_delete",
        "hands_on_artifacts_immutable_update",
        "hands_on_artifacts_immutable_delete",
        "hands_on_reviews_immutable_update",
        "hands_on_reviews_immutable_delete",
        "hands_on_cross_questions_immutable_update",
        "hands_on_cross_questions_immutable_delete",
        "trg_source_snapshots_no_update",
        "trg_source_snapshots_no_delete",
        "trg_source_snapshots_no_insert_replace",
        "trg_citations_no_update",
        "trg_citations_no_delete",
        "trg_citations_no_insert_replace",
        "trg_claims_published_no_update",
        "trg_claims_published_no_delete",
        "trg_schema_quarantines_immutable_update",
        "trg_schema_quarantines_immutable_delete",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")

    body_columns = {
        "profiles_goals_idempotency": ("response_json",),
        "roadmap_idempotency": ("response_json",),
        "diagnostics_idempotency": ("response_json",),
        "imports_idempotency": ("response_json",),
        "interview_idempotency": ("response_json",),
        "notebook_review_idempotency": ("response_json",),
        "evidence_evaluation_idempotency": ("response_json",),
        "learning_content_idempotency": ("response_json",),
        "merge_items": (
            "title",
            "summary",
            "impact",
            "resolution_explanation",
            "payload_json",
        ),
        "canonical_merge_followups": ("payload_json",),
        "interview_bundles": ("name", "generic_role", "origin"),
        "interview_bundle_items": ("question",),
        "evidence": ("summary",),
        "rubrics": ("task_context", "role_context", "level_context", "provenance"),
        "rubric_dimensions": ("name", "description", "evaluation_guidance"),
        "assessments": (
            "task_ref",
            "role_context",
            "level_context",
            "assumptions_json",
            "source_refs_json",
            "provenance_refs_json",
            "facts_json",
            "trade_offs_json",
            "citations_json",
            "ambiguities_json",
            "feedback",
            "cross_question_candidate",
            "revision_invitation",
            "warnings_json",
            "limitation_labels_json",
        ),
        "assessment_dimension_results": ("rationale", "evidence_refs_json"),
        "assessment_disputes": ("reason", "resolution_note"),
        "goal_progress_memos": (
            "coverage",
            "proficiency",
            "retention",
            "readiness",
            "explanation_json",
        ),
        "notebook_entries": ("markdown",),
        "review_items": ("prompt", "answer", "context"),
        "review_attempts": (
            "response",
            "feedback",
            "correction",
            "context_variation",
            "context_result",
        ),
        "hands_on_work": (
            "scenario_title",
            "scenario_prompt",
            "role",
            "level",
            "constraints_json",
            "scenario_source",
        ),
        "hands_on_artifacts": ("content", "cross_question_response"),
        "hands_on_reviews": ("required_limitation_label",),
        "hands_on_cross_questions": ("question", "target_gap"),
        "sources": ("title", "publisher", "canonical_url"),
        "source_snapshots": ("content_ref", "version_label", "redacted_failure"),
        "claims": ("claim_text",),
        "citations": ("locator", "note"),
        "provider_requests": ("pid", "pgid", "process_identity", "temp_path"),
        "schema_quarantines": ("raw_output_ref", "validation_errors_json"),
        "search_documents": ("title", "body", "tags"),
        "learner_profiles": ("experience", "strengths", "weaknesses"),
        "goal_workspaces": ("name", "subject", "role", "resume_position"),
        "overlay_entries": ("value_json", "reason"),
        "overlay_proposals": ("payload_json", "state_reason"),
        "overlay_proposal_decisions": ("reason",),
        "learning_states": ("explanation",),
        "learner_corrections": ("value", "reason"),
        "transferred_evidence_refs": ("rationale",),
        "diagnostic_sessions": ("setup_inputs_json", "untrusted_seed_text"),
        "diagnostic_answers": ("answer",),
        "diagnostic_preview_edits": ("value_json", "reason"),
        "import_records": ("original_content",),
        "import_statements": ("original_text", "normalized_text", "corrected_text"),
        "import_statement_decisions": ("value",),
        "generated_artifacts": ("body_ref",),
        "topic_conversation_turns": ("body",),
        "interview_runs": ("question", "hint_text", "draft"),
        "interview_turns": ("body",),
        "interview_turn_results": (
            "feedback",
            "cross_question_candidate",
            "facts",
            "trade_offs",
            "dimensions",
        ),
        "runner_confirmation_inputs": ("content_ref", "resolved_content"),
        "runner_records": (
            "argv_json",
            "pid",
            "pgid",
            "temp_path",
            "outcome_json",
            "cleanup_diagnostic",
        ),
        "runner_inputs": ("content_ref",),
        "runner_output_chunks": ("content_ref",),
        "jobs": ("payload_json", "diagnostic"),
        "job_attempts": ("process_identity", "pid", "pgid", "temp_path", "diagnostic"),
        "job_results": ("warnings_json", "diagnostic_ref"),
    }
    body_checks = {
        "notebook_review_idempotency": ("response_json_valid",),
        "evidence_evaluation_idempotency": ("response_json_valid",),
        "learning_content_idempotency": ("response_json_valid",),
        "merge_items": ("payload_json_valid",),
        "canonical_merge_followups": ("payload_json_valid",),
        "interview_bundles": (
            "name_non_blank",
            "generic_role_non_blank",
            "origin_non_blank",
        ),
        "interview_bundle_items": ("question_non_blank",),
        "rubrics": ("task_context_non_blank", "provenance_non_blank"),
        "rubric_dimensions": ("name_non_blank",),
        "assessments": (
            "assumptions_json_valid",
            "source_refs_json_valid",
            "provenance_refs_json_valid",
            "facts_json_valid",
            "trade_offs_json_valid",
            "citations_json_valid",
            "ambiguities_json_valid",
            "warnings_json_valid",
            "limitation_labels_json_valid",
        ),
        "assessment_dimension_results": ("evidence_refs_json_valid",),
        "assessment_disputes": ("reason_non_blank",),
        "goal_progress_memos": (
            "coverage_valid",
            "proficiency_valid",
            "retention_valid",
            "readiness_valid",
            "explanation_json_valid",
        ),
        "notebook_entries": ("markdown_non_blank",),
        "review_items": ("prompt_non_blank", "answer_non_blank", "usable_has_answer"),
        "review_attempts": ("response_non_blank",),
        "hands_on_work": (
            "hands_on_scenario_title_non_blank",
            "hands_on_scenario_prompt_non_blank",
            "hands_on_role_non_blank",
            "hands_on_level_non_blank",
            "hands_on_constraints_array",
            "hands_on_scenario_source_non_blank",
        ),
        "hands_on_artifacts": (
            "hands_on_artifact_content_non_blank",
            "hands_on_question_response_pair",
        ),
        "hands_on_reviews": ("hands_on_static_limitation_non_blank",),
        "hands_on_cross_questions": (
            "hands_on_question_non_blank",
            "hands_on_target_gap_non_blank",
        ),
        "sources": ("title_non_blank",),
        "source_snapshots": ("content_ref_non_blank",),
        "claims": ("claim_text_non_blank",),
        "citations": ("locator_non_blank",),
        "schema_quarantines": ("validation_errors_json_valid",),
        "goal_workspaces": (
            "name_non_blank",
            "learn_subject_required",
            "interview_role_required",
            "learn_role_absent",
            "interview_subject_absent",
        ),
        "overlay_entries": ("value_json_valid",),
        "overlay_proposals": ("payload_json_valid", "payload_json_object"),
        "learner_corrections": ("value_valid",),
        "diagnostic_sessions": (
            "untrusted_seed_kind_and_text_together",
            "setup_inputs_json_valid",
            "setup_inputs_json_object",
        ),
        "diagnostic_preview_edits": ("value_json_valid", "value_json_object"),
        "topic_conversation_turns": ("body_non_blank",),
        "interview_turns": ("body_non_blank",),
        "interview_runs": (
            "question_non_blank",
            "hint_non_blank",
            "mode_references_valid",
        ),
        "interview_turn_results": (
            "facts_json_valid",
            "trade_offs_json_valid",
            "dimensions_json_valid",
        ),
        "jobs": ("payload_json_valid",),
        "job_results": ("warnings_json_valid",),
        "generated_artifacts": ("ready_complete",),
    }
    for table, columns in body_columns.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for constraint in body_checks.get(table, ()):
                batch_op.drop_constraint(
                    batch_op.f(f"ck_{table}_{constraint}"), type_="check"
                )
            for column in columns:
                batch_op.drop_column(column)

    for table in (
        *idempotency_tables,
        "merge_items",
        "interview_bundles",
        "interview_bundle_items",
    ):
        hash_column = "response_hash" if table in idempotency_tables else "body_hash"
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(hash_column, nullable=False)

    op.execute(
        "CREATE VIRTUAL TABLE search_fts USING fts5(title, body, tags, content='search_document_bodies', content_rowid='rowid')"
    )
    op.execute("INSERT INTO search_fts(search_fts) VALUES('rebuild')")
    op.execute(
        "CREATE TRIGGER trg_search_document_bodies_ai AFTER INSERT ON search_document_bodies BEGIN INSERT INTO search_fts(rowid,title,body,tags) VALUES (new.rowid,new.title,new.body,new.tags); END"
    )
    op.execute(
        "CREATE TRIGGER trg_search_document_bodies_ad AFTER DELETE ON search_document_bodies BEGIN INSERT INTO search_fts(search_fts,rowid,title,body,tags) VALUES('delete',old.rowid,old.title,old.body,old.tags); END"
    )
    op.execute(
        "CREATE TRIGGER trg_search_document_bodies_au AFTER UPDATE ON search_document_bodies BEGIN INSERT INTO search_fts(search_fts,rowid,title,body,tags) VALUES('delete',old.rowid,old.title,old.body,old.tags); INSERT INTO search_fts(rowid,title,body,tags) VALUES(new.rowid,new.title,new.body,new.tags); END"
    )

    immutable_body_tables = (
        "overlay_entry_bodies",
        "rubric_bodies",
        "rubric_dimension_bodies",
        "assessment_bodies",
        "assessment_dimension_result_bodies",
        "assessment_dispute_bodies",
        "review_attempt_bodies",
        "hands_on_work_bodies",
        "hands_on_artifact_bodies",
        "hands_on_review_bodies",
        "hands_on_cross_question_bodies",
        "source_snapshot_bodies",
        "claim_bodies",
        "citation_bodies",
        "schema_quarantine_bodies",
        "merge_item_bodies",
        "canonical_merge_followup_bodies",
        "interview_bundle_item_bodies",
        "interview_turn_bodies",
        "interview_turn_result_bodies",
    )
    for table in immutable_body_tables:
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} body is immutable'); END"
        )
    for table in (
        "rubrics",
        "rubric_dimensions",
        "assessment_dimension_results",
        "assessment_disputes",
        "review_attempts",
        "hands_on_work",
        "hands_on_artifacts",
        "hands_on_reviews",
        "hands_on_cross_questions",
        "source_snapshots",
        "citations",
        "schema_quarantines",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} header is immutable'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} header is immutable'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_insert_replace BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, '{table} replacement is not permitted'); END"
        )
    for table in (
        "hands_on_work",
        "hands_on_artifacts",
        "hands_on_reviews",
        "hands_on_cross_questions",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_update")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_insert_replace")
        op.execute(
            f"CREATE TRIGGER {table}_immutable_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} rows are immutable'); END"
        )
        op.execute(
            f"CREATE TRIGGER {table}_immutable_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} rows are immutable'); END"
        )
    op.execute(
        "CREATE TRIGGER trg_assessments_no_delete BEFORE DELETE ON assessments BEGIN SELECT RAISE(ABORT, 'assessments are immutable'); END"
    )
    op.execute("""CREATE TRIGGER trg_assessments_lifecycle_update BEFORE UPDATE ON assessments WHEN NOT (
        OLD.derivation_excluded = 0 AND NEW.derivation_excluded = 1
        AND OLD.id IS NEW.id AND OLD.owner_id IS NEW.owner_id AND OLD.goal_id IS NEW.goal_id
        AND OLD.evidence_id IS NEW.evidence_id AND OLD.run_id IS NEW.run_id AND OLD.rubric_id IS NEW.rubric_id
        AND OLD.rubric_version IS NEW.rubric_version AND OLD.state IS NEW.state
        AND OLD.requested_capability IS NEW.requested_capability AND OLD.evaluation_method IS NEW.evaluation_method
        AND OLD.predecessor_assessment_id IS NEW.predecessor_assessment_id AND OLD.created_at IS NEW.created_at
        AND OLD.body_hash IS NEW.body_hash
        AND EXISTS (SELECT 1 FROM assessments s WHERE s.predecessor_assessment_id = OLD.id AND s.owner_id = OLD.owner_id AND s.goal_id = OLD.goal_id)
    ) BEGIN SELECT RAISE(ABORT, 'only successor-backed derivation exclusion is permitted'); END""")
    op.execute(
        "CREATE TRIGGER trg_claims_published_no_delete BEFORE DELETE ON claims WHEN OLD.status='published' BEGIN SELECT RAISE(ABORT, 'published claims are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_claims_no_insert_replace BEFORE INSERT ON claims WHEN EXISTS (SELECT 1 FROM claims WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, 'claim replacement is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_claims_published_no_update BEFORE UPDATE ON claims WHEN OLD.status='published' BEGIN SELECT RAISE(ABORT, 'published claims are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_claims_required_citation_on_published_insert BEFORE INSERT ON claims WHEN NEW.status='published' AND (NEW.sensitive=1 OR NEW.claim_type IN ('disputed','comparative','time-or-version-dependent')) BEGIN SELECT RAISE(ABORT, 'required claim must publish through pending state'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_claims_required_citation_on_publish BEFORE UPDATE OF status ON claims WHEN NEW.status='published' AND (NEW.sensitive=1 OR NEW.claim_type IN ('disputed','comparative','time-or-version-dependent')) AND NOT EXISTS (SELECT 1 FROM citations WHERE claim_id=NEW.id AND owner_id=NEW.owner_id) BEGIN SELECT RAISE(ABORT, 'required claim citation missing'); END"
    )
    op.execute("""CREATE TRIGGER trg_hands_on_artifact_body_response_pair
    AFTER INSERT ON hands_on_artifact_bodies
    WHEN NOT EXISTS (
      SELECT 1 FROM hands_on_artifacts a WHERE a.id=NEW.artifact_id
        AND a.owner_id=NEW.owner_id AND a.goal_id=NEW.goal_id
        AND ((a.response_to_question_id IS NULL AND NEW.cross_question_response IS NULL)
          OR (a.response_to_question_id IS NOT NULL AND NEW.cross_question_response IS NOT NULL))
    ) BEGIN SELECT RAISE(ABORT, 'hands_on_question_response_pair'); END""")

    with op.batch_alter_table("generated_artifacts", schema=None) as batch_op:
        batch_op.create_check_constraint(
            batch_op.f("ck_generated_artifacts_ready_complete"),
            "state != 'ready' OR (body_hash IS NOT NULL AND current_snapshot_id IS NOT NULL AND producing_job_id IS NOT NULL)",
        )
    with op.batch_alter_table("interview_runs", schema=None) as batch_op:
        batch_op.create_check_constraint(
            batch_op.f("ck_interview_runs_mode_references_valid"),
            "(mode = 'Practice' AND rubric_id IS NOT NULL AND rubric_version IS NOT NULL) OR (mode = 'Mock' AND ((rubric_id IS NULL AND rubric_version IS NULL) OR (rubric_id IS NOT NULL AND rubric_version IS NOT NULL)))",
        )
    op.execute(
        "CREATE TRIGGER trg_overlay_entries_no_update BEFORE UPDATE ON overlay_entries BEGIN SELECT RAISE(ABORT, 'overlay_entries is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_overlay_entries_no_delete BEFORE DELETE ON overlay_entries BEGIN SELECT RAISE(ABORT, 'overlay_entries is append-only: DELETE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_evidence_no_update BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence is immutable: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_evidence_no_delete BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT, 'evidence is immutable: DELETE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_evidence_no_insert_replace BEFORE INSERT ON evidence WHEN EXISTS (SELECT 1 FROM evidence WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, 'evidence is immutable: replacement is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_progress_invalidate_evidence AFTER INSERT ON evidence BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.goal_id AND owner_id=NEW.owner_id; END"
    )
    op.execute(
        "CREATE TRIGGER trg_transferred_evidence_refs_no_update BEFORE UPDATE ON transferred_evidence_refs BEGIN SELECT RAISE(ABORT, 'transferred_evidence_refs is immutable: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_transferred_evidence_refs_no_delete BEFORE DELETE ON transferred_evidence_refs BEGIN SELECT RAISE(ABORT, 'transferred_evidence_refs is immutable: DELETE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_transferred_evidence_refs_no_insert_replace BEFORE INSERT ON transferred_evidence_refs WHEN EXISTS (SELECT 1 FROM transferred_evidence_refs WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, 'transferred_evidence_refs is immutable: replacement is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_sources_no_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT, 'sources are retained'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_sources_no_insert_replace BEFORE INSERT ON sources WHEN EXISTS (SELECT 1 FROM sources WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT, 'source replacement is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_import_records_original_immutable BEFORE UPDATE ON import_records WHEN NEW.id != OLD.id OR NEW.owner_id != OLD.owner_id OR NEW.original_hash != OLD.original_hash OR NEW.type != OLD.type BEGIN SELECT RAISE(ABORT, 'import original is immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_import_records_no_delete BEFORE DELETE ON import_records BEGIN SELECT RAISE(ABORT, 'import original is immutable: DELETE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_import_record_bodies_original_immutable BEFORE UPDATE ON import_record_bodies BEGIN SELECT RAISE(ABORT, 'import original is immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_overlay_proposal_decisions_no_update BEFORE UPDATE ON overlay_proposal_decisions BEGIN SELECT RAISE(ABORT, 'overlay_proposal_decisions is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_overlay_proposal_decisions_no_delete BEFORE DELETE ON overlay_proposal_decisions BEGIN SELECT RAISE(ABORT, 'overlay_proposal_decisions is append-only: DELETE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_overlay_proposal_decision_bodies_no_update BEFORE UPDATE ON overlay_proposal_decision_bodies BEGIN SELECT RAISE(ABORT, 'overlay_proposal_decision_bodies is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_learner_corrections_no_update BEFORE UPDATE ON learner_corrections BEGIN SELECT RAISE(ABORT, 'learner_corrections is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_learner_corrections_no_delete BEFORE DELETE ON learner_corrections BEGIN SELECT RAISE(ABORT, 'learner_corrections is append-only: DELETE is not permitted'); END"
    )
    op.execute("""CREATE TRIGGER trg_learner_corrections_linear_chain BEFORE INSERT ON learner_corrections
      WHEN (NEW.supersedes_correction_id IS NULL AND EXISTS (SELECT 1 FROM learner_corrections p WHERE p.owner_id=NEW.owner_id AND p.goal_id=NEW.goal_id AND p.topic_stable_id=NEW.topic_stable_id AND NOT EXISTS (SELECT 1 FROM learner_corrections c WHERE c.supersedes_correction_id=p.id))) OR (NEW.supersedes_correction_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM learner_corrections p WHERE p.id=NEW.supersedes_correction_id AND p.owner_id=NEW.owner_id AND p.goal_id=NEW.goal_id AND p.topic_stable_id=NEW.topic_stable_id AND NOT EXISTS (SELECT 1 FROM learner_corrections c WHERE c.supersedes_correction_id=p.id))) BEGIN SELECT RAISE(ABORT, 'correction must extend the active same-scope leaf'); END""")
    op.execute(
        "CREATE TRIGGER trg_progress_invalidate_correction AFTER INSERT ON learner_corrections BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.goal_id AND owner_id=NEW.owner_id; END"
    )
    op.execute(
        "CREATE TRIGGER trg_progress_invalidate_transfer AFTER INSERT ON transferred_evidence_refs BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.goal_id AND owner_id=NEW.owner_id; END"
    )
    op.execute(
        "CREATE TRIGGER trg_progress_invalidate_state_update AFTER UPDATE ON learning_states BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.goal_id AND owner_id=NEW.owner_id; END"
    )
    op.execute(
        "CREATE TRIGGER trg_progress_invalidate_goal_graph AFTER UPDATE OF graph_version_id ON goal_workspaces BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.id AND owner_id=NEW.owner_id; END"
    )
    op.execute(
        """CREATE TRIGGER trg_progress_invalidate_assessment_insert AFTER INSERT ON assessments BEGIN DELETE FROM goal_progress_memos WHERE owner_id=NEW.owner_id AND (goal_id=NEW.goal_id OR goal_id IN (SELECT goal_id FROM transferred_evidence_refs WHERE owner_id=NEW.owner_id AND source_evidence_id=NEW.evidence_id)); END"""
    )
    op.execute(
        """CREATE TRIGGER trg_progress_invalidate_dimension_insert AFTER INSERT ON assessment_dimension_results BEGIN DELETE FROM goal_progress_memos WHERE owner_id=NEW.owner_id AND (goal_id=NEW.goal_id OR goal_id IN (SELECT t.goal_id FROM transferred_evidence_refs t JOIN assessments a ON a.id=NEW.assessment_id WHERE t.owner_id=NEW.owner_id AND t.source_evidence_id=a.evidence_id)); END"""
    )
    op.execute(
        """CREATE TRIGGER trg_progress_invalidate_assessment_update AFTER UPDATE OF derivation_excluded ON assessments BEGIN DELETE FROM goal_progress_memos WHERE owner_id=NEW.owner_id AND (goal_id=NEW.goal_id OR goal_id IN (SELECT goal_id FROM transferred_evidence_refs WHERE owner_id=NEW.owner_id AND source_evidence_id=NEW.evidence_id)); END"""
    )
    op.execute(
        """CREATE TRIGGER trg_progress_invalidate_tombstone AFTER INSERT ON evidence_tombstones BEGIN DELETE FROM goal_progress_memos WHERE owner_id=NEW.owner_id AND (goal_id=NEW.goal_id OR goal_id IN (SELECT goal_id FROM transferred_evidence_refs WHERE owner_id=NEW.owner_id AND source_evidence_id=NEW.evidence_id)); END"""
    )

    # Header rows remain immutable/append-only. Policy cleanup deletes only
    # their child body rows, except terminal operational records whose policy
    # explicitly authorizes physical expiry.
    op.execute(
        "CREATE TRIGGER trg_diagnostic_answers_no_update BEFORE UPDATE ON diagnostic_answers "
        "BEGIN SELECT RAISE(ABORT, 'diagnostic_answers is append-only: UPDATE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_diagnostic_answers_no_delete BEFORE DELETE ON diagnostic_answers "
        "BEGIN SELECT RAISE(ABORT, 'diagnostic_answers is append-only: DELETE is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_diagnostic_answers_no_insert_replace BEFORE INSERT ON diagnostic_answers "
        "WHEN EXISTS (SELECT 1 FROM diagnostic_answers WHERE id = NEW.id) "
        "BEGIN SELECT RAISE(ABORT, 'diagnostic_answers is append-only: INSERT that overwrites an existing id is not permitted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_diagnostic_answer_bodies_no_update BEFORE UPDATE ON diagnostic_answer_bodies "
        "BEGIN SELECT RAISE(ABORT, 'diagnostic answer bodies are append-only'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_job_attempts_final_immutable BEFORE UPDATE ON job_attempts "
        "WHEN OLD.ended_at IS NOT NULL OR NEW.id != OLD.id OR NEW.owner_id != OLD.owner_id OR NEW.started_at != OLD.started_at OR NEW.job_id != OLD.job_id OR NEW.attempt_number != OLD.attempt_number "
        "BEGIN SELECT RAISE(ABORT, 'completed job_attempts are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_job_results_immutable_update BEFORE UPDATE ON job_results "
        "BEGIN SELECT RAISE(ABORT, 'job_results are append-only'); END"
    )
    for table in ("interview_turns", "interview_turn_results"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} are append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} are append-only'); END"
        )
    op.execute("""
    CREATE TRIGGER trg_interview_turns_mock_feedback_withheld BEFORE INSERT ON interview_turns
    WHEN NEW.kind = 'hint' BEGIN SELECT CASE WHEN EXISTS (
      SELECT 1 FROM interview_runs r WHERE r.id = NEW.run_id AND r.owner_id = NEW.owner_id
      AND r.mode = 'Mock' AND r.state != 'completed'
    ) THEN RAISE(ABORT, 'mock_feedback_withheld') END; END
    """)
    op.execute("""
    CREATE TRIGGER trg_interview_turn_results_mock_terminal_visibility BEFORE INSERT ON interview_turn_results
    BEGIN SELECT CASE WHEN EXISTS (
      SELECT 1 FROM interview_runs r WHERE r.id = NEW.run_id AND r.owner_id = NEW.owner_id
      AND r.mode = 'Mock' AND r.state != 'completed'
    ) THEN RAISE(ABORT, 'mock_feedback_withheld') END; END
    """)
    op.execute("""
    CREATE TRIGGER trg_interview_turn_results_terminal_visibility BEFORE INSERT ON interview_turn_results
    BEGIN SELECT CASE WHEN NOT EXISTS (
      SELECT 1 FROM interview_runs r JOIN interview_turns t
        ON t.id = NEW.answer_turn_id AND t.run_id = r.id AND t.owner_id = r.owner_id
      WHERE r.id = NEW.run_id AND r.owner_id = NEW.owner_id
        AND r.mode = 'Practice' AND r.state = 'evaluating' AND t.kind = 'answer'
    ) THEN RAISE(ABORT, 'Practice result requires its submitted answer evaluation') END; END
    """)


def downgrade() -> None:
    raise NotImplementedError(
        "Policy 1.0 body separation is forward-only; schema downgrade is unsupported."
    )

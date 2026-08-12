"""immutable rubrics, assessments, disputes, and re-evaluation chains

Revision ID: c204e7a1b3d9
Revises: f58c7266c93f
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c204e7a1b3d9"
down_revision: str | Sequence[str] | None = "f58c7266c93f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _immutable(table: str, identity: str = "id = NEW.id") -> None:
    op.execute(f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END")
    op.execute(f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END")
    op.execute(f"CREATE TRIGGER trg_{table}_no_insert_replace BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE {identity}) BEGIN SELECT RAISE(ABORT, '{table} replacement is not permitted'); END")


def _owned_id_constraints(table: str, *, goal: bool = False) -> tuple[sa.Constraint, ...]:
    columns = ["id", "owner_id", *( ["goal_id"] if goal else [])]
    return (
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], name=f"fk_{table}_owner_id_owners"),
        sa.UniqueConstraint(*columns, name=f"uq_{table}_id_owner" + ("_goal" if goal else "")),
    )


def upgrade() -> None:
    op.create_table(
        "rubrics",
        sa.Column("id", sa.Text(), primary_key=True), sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("task_context", sa.Text(), nullable=False), sa.Column("capability", sa.Text(), nullable=False),
        sa.Column("role_context", sa.Text()), sa.Column("level_context", sa.Text()), sa.Column("version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False), sa.Column("provenance", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        *_owned_id_constraints("rubrics"),
        sa.UniqueConstraint("owner_id", "task_context", "capability", "role_context", "level_context", "version", name="uq_rubrics_context_version"),
        sa.CheckConstraint("length(trim(task_context)) > 0", name="task_context_non_blank"),
        sa.CheckConstraint("length(trim(capability)) > 0", name="capability_non_blank"),
        sa.CheckConstraint("length(trim(version)) > 0", name="version_non_blank"),
        sa.CheckConstraint("status IN ('fixture','approved','retired')", name="status_valid"),
        sa.CheckConstraint("length(trim(provenance)) > 0", name="provenance_non_blank"),
    )
    op.create_table(
        "rubric_dimensions",
        sa.Column("id", sa.Text(), primary_key=True), sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("rubric_id", sa.Text(), nullable=False), sa.Column("stable_dimension_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("evaluation_guidance", sa.Text(), nullable=False),
        *_owned_id_constraints("rubric_dimensions"),
        sa.ForeignKeyConstraint(["rubric_id", "owner_id"], ["rubrics.id", "rubrics.owner_id"], name="fk_rubric_dimensions_rubric_owner"),
        sa.UniqueConstraint("rubric_id", "stable_dimension_id", name="uq_rubric_dimensions_stable"),
        sa.UniqueConstraint("rubric_id", "ordinal", name="uq_rubric_dimensions_ordinal"),
        sa.CheckConstraint("length(trim(stable_dimension_id)) > 0", name="stable_id_non_blank"),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_non_blank"),
        sa.CheckConstraint("ordinal > 0", name="ordinal_positive"),
    )
    op.create_table(
        "assessments",
        sa.Column("id", sa.Text(), primary_key=True), sa.Column("owner_id", sa.Text(), nullable=False), sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("evidence_id", sa.Text(), nullable=False), sa.Column("run_id", sa.Text()), sa.Column("rubric_id", sa.Text(), nullable=False),
        sa.Column("rubric_version", sa.Text(), nullable=False), sa.Column("state", sa.Text(), nullable=False), sa.Column("task_ref", sa.Text(), nullable=False),
        sa.Column("requested_capability", sa.Text(), nullable=False), sa.Column("role_context", sa.Text()), sa.Column("level_context", sa.Text()),
        sa.Column("evaluation_method", sa.Text(), nullable=False),
        *[sa.Column(f"{name}_json", sa.Text(), nullable=False) for name in ("assumptions", "source_refs", "provenance_refs", "facts", "trade_offs", "citations", "ambiguities")],
        sa.Column("feedback", sa.Text(), nullable=False), sa.Column("cross_question_candidate", sa.Text()), sa.Column("revision_invitation", sa.Text()),
        sa.Column("warnings_json", sa.Text(), nullable=False), sa.Column("limitation_labels_json", sa.Text(), nullable=False),
        sa.Column("predecessor_assessment_id", sa.Text()), sa.Column("derivation_excluded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        *_owned_id_constraints("assessments", goal=True),
        sa.ForeignKeyConstraint(["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"], name="fk_assessments_goal_owner"),
        sa.ForeignKeyConstraint(["evidence_id", "owner_id", "goal_id"], ["evidence.id", "evidence.owner_id", "evidence.goal_id"], name="fk_assessments_evidence_owner_goal"),
        sa.ForeignKeyConstraint(["rubric_id", "owner_id"], ["rubrics.id", "rubrics.owner_id"], name="fk_assessments_rubric_owner"),
        sa.ForeignKeyConstraint(["predecessor_assessment_id", "owner_id", "goal_id"], ["assessments.id", "assessments.owner_id", "assessments.goal_id"], name="fk_assessments_predecessor_owner_goal"),
        sa.UniqueConstraint("predecessor_assessment_id", name="uq_assessments_predecessor"),
        sa.CheckConstraint("state IN ('feedback-ready','ambiguity-unresolved')", name="state_valid"),
        sa.CheckConstraint("derivation_excluded IN (0,1)", name="derivation_excluded_in_0_1"),
        *[sa.CheckConstraint(f"json_valid({name}_json)", name=f"{name}_json_valid") for name in ("assumptions", "source_refs", "provenance_refs", "facts", "trade_offs", "citations", "ambiguities", "warnings", "limitation_labels")],
    )
    op.create_index("ix_assessments_owner_goal_evidence_created", "assessments", ["owner_id", "goal_id", "evidence_id", "created_at"])
    op.create_table(
        "assessment_dimension_results",
        sa.Column("id", sa.Text(), primary_key=True), sa.Column("owner_id", sa.Text(), nullable=False), sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("assessment_id", sa.Text(), nullable=False), sa.Column("rubric_dimension_id", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False), sa.Column("rationale", sa.Text(), nullable=False), sa.Column("evidence_refs_json", sa.Text(), nullable=False),
        *_owned_id_constraints("assessment_dimension_results", goal=True),
        sa.ForeignKeyConstraint(["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"], name="fk_assessment_dimension_results_goal_owner"),
        sa.ForeignKeyConstraint(["assessment_id", "owner_id", "goal_id"], ["assessments.id", "assessments.owner_id", "assessments.goal_id"], name="fk_assessment_dimension_results_assessment_owner_goal"),
        sa.ForeignKeyConstraint(["rubric_dimension_id", "owner_id"], ["rubric_dimensions.id", "rubric_dimensions.owner_id"], name="fk_assessment_dimension_results_dimension_owner"),
        sa.UniqueConstraint("assessment_id", "rubric_dimension_id", name="uq_assessment_dimension_results_dimension"),
        sa.CheckConstraint("outcome IN ('pass','trade-off','factual-correction','ambiguity-unresolved')", name="outcome_valid"),
        sa.CheckConstraint("json_valid(evidence_refs_json)", name="evidence_refs_json_valid"),
    )
    op.create_table(
        "assessment_disputes",
        sa.Column("id", sa.Text(), primary_key=True), sa.Column("owner_id", sa.Text(), nullable=False), sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("assessment_id", sa.Text(), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.Text(), nullable=False), sa.Column("resolved_at", sa.Text()), sa.Column("resolution_note", sa.Text()),
        *_owned_id_constraints("assessment_disputes", goal=True),
        sa.ForeignKeyConstraint(["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"], name="fk_assessment_disputes_goal_owner"),
        sa.ForeignKeyConstraint(["assessment_id", "owner_id", "goal_id"], ["assessments.id", "assessments.owner_id", "assessments.goal_id"], name="fk_assessment_disputes_assessment_owner_goal"),
        sa.CheckConstraint("status IN ('requested')", name="status_valid"), sa.CheckConstraint("length(trim(reason)) > 0", name="reason_non_blank"),
    )
    op.create_table(
        "reevaluation_requests",
        sa.Column("id", sa.Text(), primary_key=True), sa.Column("owner_id", sa.Text(), nullable=False), sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("dispute_id", sa.Text(), nullable=False), sa.Column("prior_assessment_id", sa.Text(), nullable=False), sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False), sa.Column("resulting_assessment_id", sa.Text()), sa.Column("requested_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text()), sa.Column("failure_reference", sa.Text()),
        *_owned_id_constraints("reevaluation_requests", goal=True),
        sa.ForeignKeyConstraint(["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"], name="fk_reevaluation_requests_goal_owner"),
        sa.ForeignKeyConstraint(["dispute_id", "owner_id", "goal_id"], ["assessment_disputes.id", "assessment_disputes.owner_id", "assessment_disputes.goal_id"], name="fk_reevaluation_requests_dispute_owner_goal"),
        sa.ForeignKeyConstraint(["prior_assessment_id", "owner_id", "goal_id"], ["assessments.id", "assessments.owner_id", "assessments.goal_id"], name="fk_reevaluation_requests_prior_owner_goal"),
        sa.ForeignKeyConstraint(["resulting_assessment_id", "owner_id", "goal_id"], ["assessments.id", "assessments.owner_id", "assessments.goal_id"], name="fk_reevaluation_requests_result_owner_goal"),
        sa.UniqueConstraint("dispute_id", name="uq_reevaluation_requests_dispute"),
        sa.UniqueConstraint("job_id", name="uq_reevaluation_requests_job"),
        sa.CheckConstraint("status IN ('requested','completed','failed')", name="status_valid"),
        sa.CheckConstraint("status != 'completed' OR (resulting_assessment_id IS NOT NULL AND completed_at IS NOT NULL)", name="completed_has_result"),
        sa.CheckConstraint("status != 'failed' OR failure_reference IS NOT NULL", name="failed_has_reference"),
    )
    op.create_table(
        "evidence_evaluation_idempotency",
        sa.Column("id", sa.Text(), primary_key=True), sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False), sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False), sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("request_ref", sa.Text()),
        sa.Column("completed", sa.Integer(), server_default="1", nullable=False),
        *_owned_id_constraints("evidence_evaluation_idempotency"),
        sa.UniqueConstraint("owner_id", "operation", "idempotency_key", name="uq_evidence_evaluation_idempotency_command"),
        sa.CheckConstraint("length(trim(operation)) > 0", name="operation_non_blank"),
        sa.CheckConstraint("json_valid(response_json)", name="response_json_valid"),
        sa.CheckConstraint("completed IN (0,1)", name="completed_in_0_1"),
        sa.CheckConstraint("completed = 1 OR request_ref IS NOT NULL", name="reservation_has_request_ref"),
    )
    for table in ("rubrics", "rubric_dimensions", "assessment_dimension_results", "assessment_disputes"):
        _immutable(table)
    op.execute("CREATE TRIGGER trg_evidence_evaluation_idempotency_no_delete BEFORE DELETE ON evidence_evaluation_idempotency BEGIN SELECT RAISE(ABORT, 'evidence evaluation idempotency records cannot be deleted'); END")
    op.execute("CREATE TRIGGER trg_evidence_evaluation_idempotency_no_insert_replace BEFORE INSERT ON evidence_evaluation_idempotency WHEN EXISTS (SELECT 1 FROM evidence_evaluation_idempotency WHERE id = NEW.id) BEGIN SELECT RAISE(ABORT, 'evidence evaluation idempotency replacement is not permitted'); END")
    op.execute("""CREATE TRIGGER trg_evidence_evaluation_idempotency_lifecycle_update BEFORE UPDATE ON evidence_evaluation_idempotency WHEN NOT (
        OLD.completed = 0 AND NEW.completed = 1
        AND OLD.id IS NEW.id AND OLD.owner_id IS NEW.owner_id AND OLD.operation IS NEW.operation
        AND OLD.idempotency_key IS NEW.idempotency_key AND OLD.request_hash IS NEW.request_hash
        AND OLD.created_at IS NEW.created_at AND OLD.request_ref IS NEW.request_ref
        AND OLD.response_json IS NOT NEW.response_json
    ) BEGIN SELECT RAISE(ABORT, 'invalid evidence evaluation idempotency mutation'); END""")
    op.execute("CREATE TRIGGER trg_assessments_no_delete BEFORE DELETE ON assessments BEGIN SELECT RAISE(ABORT, 'assessments are immutable'); END")
    op.execute("CREATE TRIGGER trg_assessments_no_insert_replace BEFORE INSERT ON assessments WHEN EXISTS (SELECT 1 FROM assessments WHERE id = NEW.id) BEGIN SELECT RAISE(ABORT, 'assessment replacement is not permitted'); END")
    op.execute("""CREATE TRIGGER trg_assessments_linear_chain_insert BEFORE INSERT ON assessments WHEN
        (NEW.predecessor_assessment_id IS NULL AND EXISTS (
          SELECT 1 FROM assessments a WHERE a.owner_id = NEW.owner_id AND a.evidence_id = NEW.evidence_id AND a.derivation_excluded = 0
        ))
        OR (NEW.predecessor_assessment_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM assessments p WHERE p.id = NEW.predecessor_assessment_id AND p.owner_id = NEW.owner_id
          AND p.goal_id = NEW.goal_id AND p.evidence_id = NEW.evidence_id AND p.rubric_id = NEW.rubric_id
          AND p.rubric_version = NEW.rubric_version AND p.derivation_excluded = 0
        ))
        BEGIN SELECT RAISE(ABORT, 'assessment must extend the active same-scope chain tip'); END""")
    op.execute("""CREATE TRIGGER trg_assessments_lifecycle_update BEFORE UPDATE ON assessments WHEN NOT (
        OLD.derivation_excluded = 0 AND NEW.derivation_excluded = 1
        AND OLD.id IS NEW.id AND OLD.owner_id IS NEW.owner_id AND OLD.goal_id IS NEW.goal_id
        AND OLD.evidence_id IS NEW.evidence_id AND OLD.run_id IS NEW.run_id AND OLD.rubric_id IS NEW.rubric_id
        AND OLD.rubric_version IS NEW.rubric_version AND OLD.state IS NEW.state AND OLD.task_ref IS NEW.task_ref
        AND OLD.requested_capability IS NEW.requested_capability AND OLD.role_context IS NEW.role_context AND OLD.level_context IS NEW.level_context
        AND OLD.evaluation_method IS NEW.evaluation_method AND OLD.assumptions_json IS NEW.assumptions_json
        AND OLD.source_refs_json IS NEW.source_refs_json AND OLD.provenance_refs_json IS NEW.provenance_refs_json
        AND OLD.facts_json IS NEW.facts_json AND OLD.trade_offs_json IS NEW.trade_offs_json AND OLD.citations_json IS NEW.citations_json
        AND OLD.ambiguities_json IS NEW.ambiguities_json AND OLD.feedback IS NEW.feedback
        AND OLD.cross_question_candidate IS NEW.cross_question_candidate AND OLD.revision_invitation IS NEW.revision_invitation
        AND OLD.warnings_json IS NEW.warnings_json AND OLD.limitation_labels_json IS NEW.limitation_labels_json
        AND OLD.predecessor_assessment_id IS NEW.predecessor_assessment_id AND OLD.created_at IS NEW.created_at
        AND EXISTS (SELECT 1 FROM assessments s WHERE s.predecessor_assessment_id = OLD.id AND s.owner_id = OLD.owner_id AND s.goal_id = OLD.goal_id)
    ) BEGIN SELECT RAISE(ABORT, 'only successor-backed derivation exclusion is permitted'); END""")
    op.execute("CREATE TRIGGER trg_reevaluation_requests_no_delete BEFORE DELETE ON reevaluation_requests BEGIN SELECT RAISE(ABORT, 'reevaluation requests cannot be deleted'); END")
    op.execute("""CREATE TRIGGER trg_reevaluation_requests_lifecycle_update BEFORE UPDATE ON reevaluation_requests WHEN NOT (
        OLD.id IS NEW.id AND OLD.owner_id IS NEW.owner_id AND OLD.goal_id IS NEW.goal_id AND OLD.dispute_id IS NEW.dispute_id
        AND OLD.prior_assessment_id IS NEW.prior_assessment_id AND OLD.requested_at IS NEW.requested_at
        AND (
          (OLD.status = 'requested' AND NEW.status = 'completed' AND NEW.resulting_assessment_id IS NOT NULL
              AND NEW.completed_at IS NOT NULL AND NEW.failure_reference IS NULL AND OLD.job_id IS NEW.job_id)
          OR (OLD.status = 'requested' AND NEW.status = 'failed' AND NEW.failure_reference IS NOT NULL
              AND NEW.resulting_assessment_id IS NULL AND NEW.completed_at IS NULL AND OLD.job_id IS NEW.job_id)
        )
    ) BEGIN SELECT RAISE(ABORT, 'invalid reevaluation request mutation'); END""")


def downgrade() -> None:
    for table in ("evidence_evaluation_idempotency", "reevaluation_requests", "assessment_disputes", "assessment_dimension_results", "assessments", "rubric_dimensions", "rubrics"):
        op.drop_table(table)

"""fixture derived progress memo and atomic invalidation

Revision ID: e205f6a2c4d1
Revises: c204e7a1b3d9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e205f6a2c4d1"
down_revision: str | Sequence[str] | None = "c204e7a1b3d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goal_progress_memos",
        sa.Column("goal_id", sa.Text(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("coverage", sa.Text(), nullable=False),
        sa.Column("proficiency", sa.Text(), nullable=False),
        sa.Column("retention", sa.Text(), nullable=False),
        sa.Column("readiness", sa.Text(), nullable=False),
        sa.Column("explanation_json", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("derivation_version", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], name="fk_goal_progress_memos_owner_id_owners"),
        sa.ForeignKeyConstraint(["goal_id", "owner_id"], ["goal_workspaces.id", "goal_workspaces.owner_id"], name="fk_goal_progress_memos_goal_owner"),
        sa.UniqueConstraint("goal_id", "owner_id", name="uq_goal_progress_memos_goal_owner"),
        *[sa.CheckConstraint(f"{column} IN ('likely-known','partial','unverified','new')", name=f"{column}_valid") for column in ("coverage", "proficiency", "retention", "readiness")],
        sa.CheckConstraint("json_valid(explanation_json)", name="explanation_json_valid"),
        sa.CheckConstraint("length(trim(input_hash)) > 0", name="input_hash_non_blank"),
        sa.CheckConstraint("length(trim(derivation_version)) > 0", name="derivation_version_non_blank"),
    )
    # Only the active same-scope correction leaf can be extended.
    op.execute("""CREATE TRIGGER trg_learner_corrections_linear_chain BEFORE INSERT ON learner_corrections
      WHEN (NEW.supersedes_correction_id IS NULL AND EXISTS (
        SELECT 1 FROM learner_corrections p WHERE p.owner_id=NEW.owner_id AND p.goal_id=NEW.goal_id
        AND p.topic_stable_id=NEW.topic_stable_id AND NOT EXISTS (
          SELECT 1 FROM learner_corrections c WHERE c.supersedes_correction_id=p.id)))
      OR (NEW.supersedes_correction_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM learner_corrections p WHERE p.id=NEW.supersedes_correction_id
        AND p.owner_id=NEW.owner_id AND p.goal_id=NEW.goal_id AND p.topic_stable_id=NEW.topic_stable_id
        AND NOT EXISTS (SELECT 1 FROM learner_corrections c WHERE c.supersedes_correction_id=p.id)))
      BEGIN SELECT RAISE(ABORT, 'correction must extend the active same-scope leaf'); END""")
    op.execute("CREATE UNIQUE INDEX uq_learner_corrections_superseded_once ON learner_corrections(supersedes_correction_id) WHERE supersedes_correction_id IS NOT NULL")
    op.execute("CREATE TRIGGER trg_progress_invalidate_evidence AFTER INSERT ON evidence BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.goal_id AND owner_id=NEW.owner_id; END")
    op.execute("""CREATE TRIGGER trg_progress_invalidate_assessment_insert AFTER INSERT ON assessments BEGIN
      DELETE FROM goal_progress_memos WHERE owner_id=NEW.owner_id AND (goal_id=NEW.goal_id OR goal_id IN
      (SELECT goal_id FROM transferred_evidence_refs WHERE owner_id=NEW.owner_id AND source_evidence_id=NEW.evidence_id)); END""")
    op.execute("""CREATE TRIGGER trg_progress_invalidate_dimension_insert AFTER INSERT ON assessment_dimension_results BEGIN
      DELETE FROM goal_progress_memos WHERE owner_id=NEW.owner_id AND (goal_id=NEW.goal_id OR goal_id IN
      (SELECT t.goal_id FROM transferred_evidence_refs t JOIN assessments a ON a.id=NEW.assessment_id
       WHERE t.owner_id=NEW.owner_id AND t.source_evidence_id=a.evidence_id)); END""")
    op.execute("""CREATE TRIGGER trg_progress_invalidate_assessment_update AFTER UPDATE OF derivation_excluded ON assessments BEGIN
      DELETE FROM goal_progress_memos WHERE owner_id=NEW.owner_id AND (goal_id=NEW.goal_id OR goal_id IN
      (SELECT goal_id FROM transferred_evidence_refs WHERE owner_id=NEW.owner_id AND source_evidence_id=NEW.evidence_id)); END""")
    op.execute("CREATE TRIGGER trg_progress_invalidate_correction AFTER INSERT ON learner_corrections BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.goal_id AND owner_id=NEW.owner_id; END")
    op.execute("CREATE TRIGGER trg_progress_invalidate_transfer AFTER INSERT ON transferred_evidence_refs BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.goal_id AND owner_id=NEW.owner_id; END")
    op.execute("CREATE TRIGGER trg_progress_invalidate_state_update AFTER UPDATE ON learning_states BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.goal_id AND owner_id=NEW.owner_id; END")
    op.execute("CREATE TRIGGER trg_progress_invalidate_goal_graph AFTER UPDATE OF graph_version_id ON goal_workspaces BEGIN DELETE FROM goal_progress_memos WHERE goal_id=NEW.id AND owner_id=NEW.owner_id; END")
    op.execute("""CREATE TRIGGER trg_progress_invalidate_tombstone AFTER INSERT ON evidence_tombstones BEGIN
      DELETE FROM goal_progress_memos WHERE owner_id=NEW.owner_id AND (
        goal_id=NEW.goal_id OR goal_id IN (SELECT goal_id FROM transferred_evidence_refs
        WHERE owner_id=NEW.owner_id AND source_evidence_id=NEW.evidence_id)); END""")


def downgrade() -> None:
    for trigger in (
        "trg_progress_invalidate_tombstone", "trg_progress_invalidate_goal_graph", "trg_progress_invalidate_state_update",
        "trg_progress_invalidate_transfer", "trg_progress_invalidate_correction",
        "trg_progress_invalidate_assessment_update", "trg_progress_invalidate_dimension_insert", "trg_progress_invalidate_assessment_insert",
        "trg_progress_invalidate_evidence", "trg_learner_corrections_linear_chain",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.execute("DROP INDEX IF EXISTS uq_learner_corrections_superseded_once")
    op.drop_table("goal_progress_memos")

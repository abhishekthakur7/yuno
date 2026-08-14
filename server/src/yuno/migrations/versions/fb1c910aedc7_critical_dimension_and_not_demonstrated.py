"""Fifth outcome vocabulary member and critical-dimension flag (IDK-204/IDK-009 section 6, 9.2).

Adds `not-demonstrated` to `assessment_dimension_results.outcome`'s closed
vocabulary (IDK-009 section 6's five-value list was previously shipped with
only four) and adds `assessment_dimension_results.is_critical`, the
persisted flag the critical-dimension precedence rule in section 9.2
depends on.

`is_critical` lives only here, not on `rubric_dimensions`: IDK-009 section 6
fixes criticality per `stable_dimension_id`, invariant across all three
rubric versions, so `RubricDimension.is_critical` derives it from the
already-stored `stable_dimension_id` (see
`yuno.modules.evidence_evaluation.domain.CRITICAL_STABLE_DIMENSION_IDS`)
rather than persisting an independent, settable flag a rubric manifest
could omit or get wrong. `AssessmentDimensionResult` has no
`stable_dimension_id` of its own (only the opaque `rubric_dimension_id`),
so its `is_critical` is a deliberate denormalization of the referenced
rubric dimension's derived flag at assessment time -- it is genuinely read
by the pure `derive_progress` rollup, which has no database access to
join back to the rubric.

`assessment_dimension_results` carries hand-written immutability triggers
(`c204e7a1b3d9`, re-created by `e10d1a0c0100`) plus
`trg_progress_invalidate_dimension_insert` (`e205f6a2c4d1`, re-created
verbatim by `e10d1a0c0100`), none of which are part of `Base.metadata`, so
SQLite's batch "copy and swap" rebuild -- required here since it is both
widening a CHECK constraint and adding a column with its own CHECK --
drops them along with the table it replaces. They are re-created verbatim
afterward.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "fb1c910aedc7"
down_revision: str | None = "c5b1e70a94d2"
branch_labels: str | None = None
depends_on: str | None = None

_TABLE = "assessment_dimension_results"

_INVALIDATE_DIMENSION_INSERT_SQL = (
    "CREATE TRIGGER trg_progress_invalidate_dimension_insert "
    f"AFTER INSERT ON {_TABLE} BEGIN "
    "DELETE FROM goal_progress_memos WHERE owner_id=NEW.owner_id AND "
    "(goal_id=NEW.goal_id OR goal_id IN "
    "(SELECT t.goal_id FROM transferred_evidence_refs t "
    "JOIN assessments a ON a.id=NEW.assessment_id "
    "WHERE t.owner_id=NEW.owner_id AND t.source_evidence_id=a.evidence_id)); END"
)


def _drop_triggers() -> None:
    for trigger in (
        f"trg_{_TABLE}_no_update",
        f"trg_{_TABLE}_no_delete",
        f"trg_{_TABLE}_no_insert_replace",
        "trg_progress_invalidate_dimension_insert",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")


def _create_triggers() -> None:
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}_no_update BEFORE UPDATE ON {_TABLE} "
        f"BEGIN SELECT RAISE(ABORT, '{_TABLE} header is immutable'); END"
    )
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}_no_delete BEFORE DELETE ON {_TABLE} "
        f"BEGIN SELECT RAISE(ABORT, '{_TABLE} header is immutable'); END"
    )
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}_no_insert_replace BEFORE INSERT ON {_TABLE} "
        f"WHEN EXISTS (SELECT 1 FROM {_TABLE} WHERE id=NEW.id) "
        f"BEGIN SELECT RAISE(ABORT, '{_TABLE} replacement is not permitted'); END"
    )
    op.execute(_INVALIDATE_DIMENSION_INSERT_SQL)


def upgrade() -> None:
    _drop_triggers()

    with op.batch_alter_table(_TABLE) as batch:
        batch.drop_constraint("outcome_valid", type_="check")
        batch.create_check_constraint(
            "outcome_valid",
            "outcome IN ('pass','trade-off','factual-correction','not-demonstrated','ambiguity-unresolved')",
        )
        batch.add_column(
            sa.Column("is_critical", sa.Integer(), server_default="0", nullable=False)
        )
        batch.create_check_constraint("is_critical_in_0_1", "is_critical IN (0,1)")

    _create_triggers()


def downgrade() -> None:
    _drop_triggers()

    with op.batch_alter_table(_TABLE) as batch:
        batch.drop_constraint("is_critical_in_0_1", type_="check")
        batch.drop_column("is_critical")
        batch.drop_constraint("outcome_valid", type_="check")
        batch.create_check_constraint(
            "outcome_valid",
            "outcome IN ('pass','trade-off','factual-correction','ambiguity-unresolved')",
        )

    _create_triggers()

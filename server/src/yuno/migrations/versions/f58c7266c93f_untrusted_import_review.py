"""untrusted import review

Revision ID: f58c7266c93f
Revises: f7b2c9d1e4a6
Create Date: 2026-08-12 12:59:23.615019

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f58c7266c93f"
down_revision: str | Sequence[str] | None = "f7b2c9d1e4a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imports_idempotency",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(operation)) > 0",
            name=op.f("ck_imports_idempotency_operation_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_imports_idempotency_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_imports_idempotency")),
        sa.UniqueConstraint("id", "owner_id", name="uq_imports_idempotency_id_owner"),
        sa.UniqueConstraint(
            "owner_id",
            "operation",
            "idempotency_key",
            name="uq_imports_idempotency_command",
        ),
    )
    op.create_table(
        "import_records",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("original_content", sa.LargeBinary(), nullable=False),
        sa.Column("original_hash", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_reference", sa.Text(), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('selected','parsing','parsed-untrusted','learner-review','applied','failed','cancelled')",
            name=op.f("ck_import_records_status_valid"),
        ),
        sa.CheckConstraint(
            "type IN ('markdown','plain_text')",
            name=op.f("ck_import_records_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_import_records_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_import_records_owner_id_owners")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_records")),
        sa.UniqueConstraint("id", "owner_id", name="uq_import_records_id_owner"),
    )
    with op.batch_alter_table("import_records", schema=None) as batch_op:
        batch_op.create_index(
            "ix_import_records_owner_goal_created",
            ["owner_id", "goal_id", "created_at"],
            unique=False,
        )

    op.create_table(
        "topic_import_hashes",
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("graph_version_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text(), nullable=False),
        sa.Column("imports_hash", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_topic_import_hashes_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["graph_version_id", "topic_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_topic_import_hashes_topic",
        ),
        sa.ForeignKeyConstraint(
            ["graph_version_id"],
            ["editorial_approvals.graph_version_id"],
            name=op.f("fk_topic_import_hashes_graph_version_id_editorial_approvals"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_topic_import_hashes_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint(
            "owner_id",
            "goal_id",
            "graph_version_id",
            "topic_stable_id",
            name=op.f("pk_topic_import_hashes"),
        ),
    )
    op.create_table(
        "import_statements",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("import_id", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("original_hash", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("normalized_hash", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("duplicate_of_statement_id", sa.Text(), nullable=True),
        sa.Column("trust_state", sa.Text(), nullable=False),
        sa.Column("mapping_state", sa.Text(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "mapping_state IN ('unmapped','mapped','duplicate')",
            name=op.f("ck_import_statements_mapping_state_valid"),
        ),
        sa.CheckConstraint(
            "trust_state IN ('untrusted','verified','dismissed')",
            name=op.f("ck_import_statements_trust_state_valid"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_import_statements_confidence_range"),
        ),
        sa.CheckConstraint(
            "sequence > 0", name=op.f("ck_import_statements_sequence_positive")
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_statement_id", "owner_id"],
            ["import_statements.id", "import_statements.owner_id"],
            name="fk_import_statements_duplicate_owner",
        ),
        sa.ForeignKeyConstraint(
            ["import_id", "owner_id"],
            ["import_records.id", "import_records.owner_id"],
            name="fk_import_statements_import_owner",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_import_statements_owner_id_owners"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_statements")),
        sa.UniqueConstraint("id", "owner_id", name="uq_import_statements_id_owner"),
        sa.UniqueConstraint(
            "import_id",
            "parser_version",
            "sequence",
            name="uq_import_statements_occurrence",
        ),
    )
    with op.batch_alter_table("import_statements", schema=None) as batch_op:
        batch_op.create_index(
            "ix_import_statements_owner_import_sequence",
            ["owner_id", "import_id", "parser_version", "sequence"],
            unique=False,
        )
        batch_op.create_index(
            "uq_import_statements_unmapped_hash",
            ["owner_id", "parser_version", "normalized_hash"],
            unique=True,
            sqlite_where=sa.text("mapping_state = 'unmapped'"),
        )

    op.create_table(
        "import_statement_decisions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("statement_id", sa.Text(), nullable=False),
        sa.Column("decision_type", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "decision_type IN ('corrected','verified','dismissed')",
            name=op.f("ck_import_statement_decisions_decision_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_import_statement_decisions_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["statement_id", "owner_id"],
            ["import_statements.id", "import_statements.owner_id"],
            name="fk_import_statement_decisions_statement_owner",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_statement_decisions")),
        sa.UniqueConstraint(
            "id", "owner_id", name="uq_import_statement_decisions_id_owner"
        ),
    )
    op.create_table(
        "import_statement_mappings",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("statement_id", sa.Text(), nullable=False),
        sa.Column("topic_stable_id", sa.Text(), nullable=False),
        sa.Column("graph_version_id", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "decision IN ('approved','revoked')",
            name=op.f("ck_import_statement_mappings_decision_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_import_statement_mappings_goal_owner",
        ),
        sa.ForeignKeyConstraint(
            ["graph_version_id", "topic_stable_id"],
            ["topics.graph_version_id", "topics.stable_id"],
            name="fk_import_statement_mappings_topic",
        ),
        sa.ForeignKeyConstraint(
            ["graph_version_id"],
            ["editorial_approvals.graph_version_id"],
            name=op.f(
                "fk_import_statement_mappings_graph_version_id_editorial_approvals"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name=op.f("fk_import_statement_mappings_owner_id_owners"),
        ),
        sa.ForeignKeyConstraint(
            ["statement_id", "owner_id"],
            ["import_statements.id", "import_statements.owner_id"],
            name="fk_import_statement_mappings_statement_owner",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_statement_mappings")),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            "goal_id",
            name="uq_import_statement_mappings_id_owner_goal",
        ),
    )
    with op.batch_alter_table("import_statement_mappings", schema=None) as batch_op:
        batch_op.create_index(
            "uq_import_statement_mappings_active",
            ["owner_id", "statement_id"],
            unique=True,
            sqlite_where=sa.text("decision = 'approved' AND revoked_at IS NULL"),
        )

    op.execute(
        "CREATE TRIGGER trg_import_records_original_immutable BEFORE UPDATE ON import_records "
        "WHEN NEW.id != OLD.id OR NEW.owner_id != OLD.owner_id "
        "OR NEW.original_content IS NOT OLD.original_content "
        "OR NEW.original_hash != OLD.original_hash OR NEW.type != OLD.type "
        "BEGIN SELECT RAISE(ABORT, 'import original is immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_import_records_no_delete BEFORE DELETE ON import_records "
        "BEGIN SELECT RAISE(ABORT, 'import original is immutable: DELETE is not permitted'); END"
    )
    for table in (
        "import_statement_decisions",
        "imports_idempotency",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only: UPDATE is not permitted'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only: DELETE is not permitted'); END"
        )
    op.execute(
        "CREATE TRIGGER trg_import_statement_mappings_governed_update BEFORE UPDATE ON import_statement_mappings "
        "WHEN NEW.id != OLD.id OR NEW.owner_id != OLD.owner_id OR NEW.goal_id != OLD.goal_id "
        "OR NEW.statement_id != OLD.statement_id OR NEW.topic_stable_id != OLD.topic_stable_id "
        "OR NEW.graph_version_id != OLD.graph_version_id OR NEW.decision != OLD.decision "
        "OR NEW.accepted_at != OLD.accepted_at OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL "
        "BEGIN SELECT RAISE(ABORT, 'import mapping permits only first revocation'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_import_statement_mappings_no_delete BEFORE DELETE ON import_statement_mappings "
        "BEGIN SELECT RAISE(ABORT, 'import_statement_mappings is append-only: DELETE is not permitted'); END"
    )
def downgrade() -> None:
    for table in (
        "imports_idempotency",
        "import_statement_decisions",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_update")
    op.execute("DROP TRIGGER IF EXISTS trg_import_statement_mappings_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_import_statement_mappings_governed_update")
    op.execute("DROP TRIGGER IF EXISTS trg_import_records_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_import_records_original_immutable")
    with op.batch_alter_table("import_statement_mappings", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_import_statement_mappings_active",
            sqlite_where=sa.text("decision = 'approved' AND revoked_at IS NULL"),
        )

    op.drop_table("import_statement_mappings")
    op.drop_table("import_statement_decisions")
    with op.batch_alter_table("import_statements", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_import_statements_unmapped_hash",
            sqlite_where=sa.text("mapping_state = 'unmapped'"),
        )
        batch_op.drop_index("ix_import_statements_owner_import_sequence")

    op.drop_table("import_statements")
    op.drop_table("topic_import_hashes")
    with op.batch_alter_table("import_records", schema=None) as batch_op:
        batch_op.drop_index("ix_import_records_owner_goal_created")

    op.drop_table("import_records")
    op.drop_table("imports_idempotency")

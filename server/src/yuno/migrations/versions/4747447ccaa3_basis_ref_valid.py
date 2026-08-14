"""basis_ref JSON validity CHECK constraint (IDK-002 section 8 item 1; IDK-503 finding B2 part a).

Adds `CheckConstraint("json_valid(basis_ref)", name="basis_ref_valid")` to
`EditorialApprovalRow`, mirroring the existing `payload_json_valid` pattern
elsewhere in the schema (e.g. `merge_item_bodies`,
`canonical_merge_followup_bodies`). `basis_ref`'s free-form column stays;
only the validation contract changes -- IDK-002 section 8 explicitly notes
there is no fallback preserved for the old any-string acceptance behavior.

`editorial_approvals` carries three hand-written raw-SQL conditional
immutability triggers (`trg_editorial_approvals_no_update`,
`trg_editorial_approvals_no_delete`,
`trg_editorial_approvals_no_insert_replace`), created by
`87af9746aec1_canonical_graph.py` and none of which are part of
`Base.metadata`. `migrations/env.py` sets `render_as_batch=True`, so the
`op.batch_alter_table` rebuild this CHECK constraint requires would
silently drop them; they are dropped explicitly first and re-created
verbatim (same WHEN guards, same RAISE bodies) afterward, in both
`upgrade()` and `downgrade()`, following the drop-triggers ->
batch_alter -> recreate-triggers idiom the previous revision (the one
this one's `down_revision` points at) established for
`assessment_dimension_results`. (Deliberately not spelling that
revision's id out again here: `tests/integration/test_alembic_migration_
failure.py`'s `_rewire_down_revision` helper does a first-match text
substitution of the id over this whole file, and an earlier prose
mention of it above the `down_revision` assignment below was shadowing
that assignment and corrupting the test's scratch branch chain.)

`editorial_approvals` is also the FK target of several tables'
`graph_version_id` columns (`server/src/yuno/modules/canonical/models.py`,
`.../diagnostics/models.py`, `.../imports/models.py`,
`.../roadmap/models.py`), so on a database that already has rows in both
`editorial_approvals` and any of those referencing tables, with
`PRAGMA foreign_keys=ON` (the default this project's connections always
run with -- see `yuno.shared.infrastructure.database`), the batch
rebuild's internal `DROP TABLE editorial_approvals` violates the inbound
foreign key. SQLite's documented procedure for its 12-step ALTER TABLE
is to toggle `PRAGMA foreign_keys` around the rebuild, and that pragma is
a no-op inside a transaction -- `migrations/env.py` runs the whole
migration batch inside one outer transaction
(`context.begin_transaction()`), so toggling it takes
`op.get_context().autocommit_block()` (Alembic's documented escape hatch
for statements that must run with no pending transaction): it commits
the outer transaction, switches the connection to
`isolation_level="AUTOCOMMIT"` for the duration of the `with` block, then
resumes a fresh transaction on exit. `upgrade()`/`downgrade()` wrap
`PRAGMA foreign_keys=OFF` .. the batch rebuild .. `PRAGMA
foreign_keys=ON` in exactly that block.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "4747447ccaa3"
down_revision: str | Sequence[str] | None = "fb1c910aedc7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "editorial_approvals"

_UPDATE_DELETE_WHEN = (
    "(SELECT status FROM canonical_graph_versions "
    "WHERE id = OLD.graph_version_id) = 'published'"
)
_INSERT_REPLACE_WHEN = (
    f"EXISTS (SELECT 1 FROM {_TABLE} WHERE id = NEW.id "
    f"AND (SELECT status FROM canonical_graph_versions "
    f"WHERE id = {_TABLE}.graph_version_id) = 'published')"
)


def _drop_triggers() -> None:
    for trigger in (
        f"trg_{_TABLE}_no_insert_replace",
        f"trg_{_TABLE}_no_delete",
        f"trg_{_TABLE}_no_update",
    ):
        op.execute(f"DROP TRIGGER {trigger}")


def _create_triggers() -> None:
    op.execute(
        f"""
        CREATE TRIGGER trg_{_TABLE}_no_update
        BEFORE UPDATE ON {_TABLE}
        WHEN {_UPDATE_DELETE_WHEN}
        BEGIN
            SELECT RAISE(ABORT, '{_TABLE} row belongs to a published canonical graph version: UPDATE is not permitted');
        END;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_{_TABLE}_no_delete
        BEFORE DELETE ON {_TABLE}
        WHEN {_UPDATE_DELETE_WHEN}
        BEGIN
            SELECT RAISE(ABORT, '{_TABLE} row belongs to a published canonical graph version: DELETE is not permitted');
        END;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_{_TABLE}_no_insert_replace
        BEFORE INSERT ON {_TABLE}
        WHEN {_INSERT_REPLACE_WHEN}
        BEGIN
            SELECT RAISE(ABORT, '{_TABLE} row belongs to a published canonical graph version: INSERT that overwrites an existing row is not permitted');
        END;
        """
    )


def upgrade() -> None:
    _drop_triggers()

    with op.get_context().autocommit_block():
        op.execute("PRAGMA foreign_keys=OFF")
        with op.batch_alter_table(_TABLE) as batch:
            batch.create_check_constraint("basis_ref_valid", "json_valid(basis_ref)")
        op.execute("PRAGMA foreign_keys=ON")

    _create_triggers()


def downgrade() -> None:
    _drop_triggers()

    with op.get_context().autocommit_block():
        op.execute("PRAGMA foreign_keys=OFF")
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_constraint("basis_ref_valid", type_="check")
        op.execute("PRAGMA foreign_keys=ON")

    _create_triggers()

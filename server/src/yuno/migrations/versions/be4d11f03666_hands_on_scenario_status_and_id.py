"""hands_on_work scenario_status widened to admit 'approved'; scenario_id header column (IDK-503 findings B10/B12).

Widens `HandsOnWorkRow`'s `hands_on_scenario_status_valid` CHECK from
`scenario_status IN ('fixture')` to `scenario_status IN
('fixture','approved')`, and adds a nullable `scenario_id` TEXT column to
`hands_on_work`'s header row.

`'approved'` is a naming choice this migration makes, not a literal
IDK-009 specifies: IDK-009 never names a field called `scenario_status`
and supplies no non-fixture status literal for it. The word is anchored
in IDK-009 section 11's own opposition -- "enforce approved
scenario/rubric/mapping/pair matching; reject fixture/unapproved content
in authoritative flows" -- not in a table the decision defines.

`scenario_id` lands on `hands_on_work` (the header row), not
`hands_on_work_bodies`: `e10d1a0c0100_policy_1_0_body_separation_and_
retention.py`'s body-separation pattern reserves the `_bodies` table for
`body_hash`-covered prose (`scenario_title`, `scenario_prompt`, `role`,
`level`, `constraints_json`, `scenario_source`), while identity/status
columns (`topic_stable_id`, `scenario_status`) stay on the header;
`scenario_id` is identity, not prose. The column is nullable and carries
no format/regex CHECK: no approved scenario records exist yet, existing
rows have no scenario identity, and IDK-009 gives twelve example
`scenario_id` values (section 4) but states no grammar for the field, so
constraining its shape would invent a rule the decision does not state.
This is unrelated to IDK-009 section 8.1's `scenario_id` requirement on
*assessments* (a different table, a separate unimplemented feature per
section 11's IDK-204 item) -- that field stays out of scope here.

`hands_on_work` carries two custom-named immutability triggers,
`hands_on_work_immutable_update` and `hands_on_work_immutable_delete`
(created by `e10d1a0c0100_policy_1_0_body_separation_and_retention.py`;
there is no insert-replace variant). `migrations/env.py` sets
`render_as_batch=True`, so the `op.batch_alter_table` rebuild this CHECK
widening and column addition require would silently drop both triggers;
they are dropped explicitly first and re-created verbatim afterward, in
both `upgrade()` and `downgrade()`.

`hands_on_work` is also the FK target of `hands_on_artifacts.work_id`
and `hands_on_work_bodies.work_id`, so on a database with rows in either,
with `PRAGMA foreign_keys=ON` (the default this project's connections
always run with -- see `yuno.shared.infrastructure.database`), the batch
rebuild's internal `DROP TABLE hands_on_work` violates those inbound
foreign keys. Following the idiom the previous revision (the one this
one's `down_revision` points at) established: `PRAGMA foreign_keys` is a
no-op inside a transaction, and `migrations/env.py` runs the whole
migration batch inside one outer transaction, so toggling it takes
`op.get_context().autocommit_block()` (Alembic's documented escape hatch
for statements that must run with no pending transaction) around
`PRAGMA foreign_keys=OFF` .. the batch rebuild .. `PRAGMA
foreign_keys=ON`.

(Deliberately not spelling that previous revision's id out again here:
`tests/integration/test_alembic_migration_failure.py`'s
`_rewire_down_revision` helper does a first-match text substitution of
the id over this whole file, and a prose mention of it above the
`down_revision` assignment below would shadow that assignment and
corrupt the test's scratch branch chain.)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "be4d11f03666"
down_revision: str | Sequence[str] | None = "4cb74877e4ba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "hands_on_work"


def _drop_triggers() -> None:
    op.execute(f"DROP TRIGGER {_TABLE}_immutable_update")
    op.execute(f"DROP TRIGGER {_TABLE}_immutable_delete")


def _create_triggers() -> None:
    op.execute(
        f"CREATE TRIGGER {_TABLE}_immutable_update BEFORE UPDATE ON {_TABLE} "
        f"BEGIN SELECT RAISE(ABORT, '{_TABLE} rows are immutable'); END"
    )
    op.execute(
        f"CREATE TRIGGER {_TABLE}_immutable_delete BEFORE DELETE ON {_TABLE} "
        f"BEGIN SELECT RAISE(ABORT, '{_TABLE} rows are immutable'); END"
    )


def upgrade() -> None:
    _drop_triggers()

    with op.get_context().autocommit_block():
        op.execute("PRAGMA foreign_keys=OFF")
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            batch_op.add_column(sa.Column("scenario_id", sa.Text()))
            batch_op.drop_constraint("hands_on_scenario_status_valid", type_="check")
            batch_op.create_check_constraint(
                "hands_on_scenario_status_valid",
                "scenario_status IN ('fixture','approved')",
            )
        op.execute("PRAGMA foreign_keys=ON")

    _create_triggers()


def downgrade() -> None:
    _drop_triggers()

    with op.get_context().autocommit_block():
        op.execute("PRAGMA foreign_keys=OFF")
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            batch_op.drop_constraint("hands_on_scenario_status_valid", type_="check")
            batch_op.create_check_constraint(
                "hands_on_scenario_status_valid", "scenario_status IN ('fixture')"
            )
            batch_op.drop_column("scenario_id")
        op.execute("PRAGMA foreign_keys=ON")

    _create_triggers()

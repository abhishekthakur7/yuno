"""sources license_status/withdrawal_reason/superseded_by_source_id (IDK-003 section 12 item 1; IDK-503 finding B7).

Adds three things to `SourceRow` per IDK-003 section 12 item 1:

- A CHECK on `license_status` enumerating exactly the production
  vocabulary fixed by section 11: `approved-open-license` /
  `approved-link-only`. The prior `license_status_non_blank` CHECK
  (any non-blank string) is dropped -- the new enumeration CHECK is
  strictly stronger, so keeping both would be redundant.
- A nullable `withdrawal_reason` column, CHECK-constrained to section
  11's five-value vocabulary (`license-revoked`,
  `license-changed-incompatible`, `publisher-retracted`,
  `factually-superseded`, `registry-declined`), plus a second CHECK
  expressing section 8's biconditional: `withdrawal_reason` is non-NULL
  if and only if `availability_status = 'withdrawn'`.
- A nullable `superseded_by_source_id` column with a self-referential
  FK. `sources`'s primary key is the single column `id`
  (`shared/infrastructure/base.id_column()`, `primary_key=True` by
  default); `uq_sources_id_owner` is a *second*, non-PK unique
  constraint added only so other owner-scoped tables
  (`source_snapshots`, `source_retrieval_commands`, `citations`,
  `source_bodies`) can FK against `(sources.id, sources.owner_id)`
  instead of `sources.id` alone. `superseded_by_source_id` follows that
  same established convention rather than a bare `sources.id` FK: the
  composite target enforces that a withdrawn source can only be
  superseded by a source under the *same* `owner_id`, which a
  single-column FK to `sources.id` would not enforce.

`sources` carries two hand-written raw-SQL triggers,
`trg_sources_no_delete` and `trg_sources_no_insert_replace` (created by
`e10d1a0c0100_policy_1_0_body_separation_and_retention.py`); there is no
`no_update` trigger -- `sources` is deliberately a mutable-header table.
`migrations/env.py` sets `render_as_batch=True`, so the
`op.batch_alter_table` rebuild these changes require would silently drop
both triggers; they are dropped explicitly first and re-created verbatim
afterward, in both `upgrade()` and `downgrade()`.

`sources` is also the FK target of `citations`, `notebook_entries`,
`source_bodies`, `source_retrieval_commands`, and `source_snapshots`, so
on a database with rows in any of those, with `PRAGMA foreign_keys=ON`
(the default this project's connections always run with -- see
`yuno.shared.infrastructure.database`), the batch rebuild's internal
`DROP TABLE sources` violates those inbound foreign keys. Following the
idiom the previous revision (the one this one's `down_revision` points
at) established: `PRAGMA foreign_keys` is a no-op inside a transaction,
and `migrations/env.py` runs the whole migration batch inside one outer
transaction, so toggling it takes `op.get_context().autocommit_block()`
(Alembic's documented escape hatch for statements that must run with no
pending transaction) around `PRAGMA foreign_keys=OFF` .. the batch
rebuild .. `PRAGMA foreign_keys=ON`.

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

revision: str = "4cb74877e4ba"
down_revision: str | Sequence[str] | None = "4747447ccaa3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "sources"

_WITHDRAWAL_REASON_VALID = (
    "withdrawal_reason IN ("
    "'license-revoked',"
    "'license-changed-incompatible',"
    "'publisher-retracted',"
    "'factually-superseded',"
    "'registry-declined'"
    ") OR withdrawal_reason IS NULL"
)
_WITHDRAWAL_REASON_REQUIRED_IFF_WITHDRAWN = (
    "(availability_status = 'withdrawn') = (withdrawal_reason IS NOT NULL)"
)


def _drop_triggers() -> None:
    op.execute(f"DROP TRIGGER trg_{_TABLE}_no_delete")
    op.execute(f"DROP TRIGGER trg_{_TABLE}_no_insert_replace")


def _create_triggers() -> None:
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}_no_delete BEFORE DELETE ON {_TABLE} "
        "BEGIN SELECT RAISE(ABORT, 'sources are retained'); END"
    )
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}_no_insert_replace BEFORE INSERT ON {_TABLE} "
        f"WHEN EXISTS (SELECT 1 FROM {_TABLE} WHERE id=NEW.id) "
        "BEGIN SELECT RAISE(ABORT, 'source replacement is not permitted'); END"
    )


def upgrade() -> None:
    _drop_triggers()

    with op.get_context().autocommit_block():
        op.execute("PRAGMA foreign_keys=OFF")
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            batch_op.add_column(sa.Column("withdrawal_reason", sa.Text()))
            batch_op.add_column(sa.Column("superseded_by_source_id", sa.Text()))
            batch_op.drop_constraint("license_status_non_blank", type_="check")
            batch_op.create_check_constraint(
                "license_status_valid",
                "license_status IN ('approved-open-license','approved-link-only')",
            )
            batch_op.create_check_constraint(
                "withdrawal_reason_valid", _WITHDRAWAL_REASON_VALID
            )
            batch_op.create_check_constraint(
                "withdrawal_reason_required_iff_withdrawn",
                _WITHDRAWAL_REASON_REQUIRED_IFF_WITHDRAWN,
            )
            batch_op.create_foreign_key(
                "fk_sources_superseded_by_source_owner",
                _TABLE,
                ["superseded_by_source_id", "owner_id"],
                ["id", "owner_id"],
            )
        op.execute("PRAGMA foreign_keys=ON")

    _create_triggers()


def downgrade() -> None:
    _drop_triggers()

    with op.get_context().autocommit_block():
        op.execute("PRAGMA foreign_keys=OFF")
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            batch_op.drop_constraint(
                "fk_sources_superseded_by_source_owner", type_="foreignkey"
            )
            batch_op.drop_constraint(
                "withdrawal_reason_required_iff_withdrawn", type_="check"
            )
            batch_op.drop_constraint("withdrawal_reason_valid", type_="check")
            batch_op.drop_constraint("license_status_valid", type_="check")
            batch_op.create_check_constraint(
                "license_status_non_blank", "length(trim(license_status)) > 0"
            )
            batch_op.drop_column("superseded_by_source_id")
            batch_op.drop_column("withdrawal_reason")
        op.execute("PRAGMA foreign_keys=ON")

    _create_triggers()

"""canonical graph

Revision ID: 87af9746aec1
Revises: 442e2f56adb9
Create Date: 2026-08-11 19:49:36.987302

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '87af9746aec1'
down_revision: str | Sequence[str] | None = '442e2f56adb9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Immutability guard (spec §4.3's closing line; IDK-102 "Data and
# invariants"): UPDATE/DELETE must be rejected on any
# canonical_graph_versions/topics/topic_relations/content_revisions/
# editorial_approvals row belonging to an APPROVED (i.e. `published`,
# spec §9.1) version. Unlike `442e2f56adb9`'s `audit_events` triggers
# (unconditional -- every row is append-only forever), these are
# *conditional*: a row belonging to a not-yet-published version may still
# be corrected/removed before publication; only a published version's
# rows become permanently immutable.
#
# `canonical_graph_versions` checks `OLD.status` directly. The other four
# tables have no `status` column of their own, so their triggers look up
# their owning version's status via a scalar subquery on
# `graph_version_id` (or, for `editorial_approvals`, the version it
# approves).
#
# See `442e2f56adb9` for why a BEFORE INSERT `no_insert_replace` trigger
# is needed on top of UPDATE/DELETE triggers (SQLite's `INSERT OR
# REPLACE` bypasses both without `PRAGMA recursive_triggers`). Here the
# `no_insert_replace` guard looks up the status of the *existing* row
# that would be overwritten (by primary key), not `NEW`'s -- `NEW.graph_version_id`
# is attacker-controlled and not trustworthy, but the existing row's
# owning version's status is. It stays conditional like the UPDATE/DELETE
# guards: an insert that replaces a row belonging to a not-yet-published
# version is legitimate (the publisher may do this, in one transaction,
# before publication) and must not be blocked.
#
# WARNING (see `442e2f56adb9`): `migrations/env.py` sets
# `render_as_batch=True`, which silently drops raw-SQL triggers on any
# `batch_alter_table(<one of these five tables>, ...)`. That migration
# must explicitly recreate them afterward -- see
# `tests/integration/test_canonical_immutability.py`'s trigger-existence
# test.

_CONDITIONAL_APPROVED_TRIGGERS: tuple[tuple[str, str, str, str], ...] = (
    # (table, no_update_trigger_name, no_delete_trigger_name,
    # no_insert_replace_trigger_name) -- the WHEN guard differs per table
    # (see _trigger_when/_insert_trigger_when below), so name tuples are
    # generated, not the guard text.
    (
        "canonical_graph_versions",
        "trg_canonical_graph_versions_no_update",
        "trg_canonical_graph_versions_no_delete",
        "trg_canonical_graph_versions_no_insert_replace",
    ),
    ("topics", "trg_topics_no_update", "trg_topics_no_delete", "trg_topics_no_insert_replace"),
    (
        "topic_relations",
        "trg_topic_relations_no_update",
        "trg_topic_relations_no_delete",
        "trg_topic_relations_no_insert_replace",
    ),
    (
        "content_revisions",
        "trg_content_revisions_no_update",
        "trg_content_revisions_no_delete",
        "trg_content_revisions_no_insert_replace",
    ),
    (
        "editorial_approvals",
        "trg_editorial_approvals_no_update",
        "trg_editorial_approvals_no_delete",
        "trg_editorial_approvals_no_insert_replace",
    ),
)


def _trigger_when(table: str) -> str:
    """The `WHEN` guard for `table`'s no-update/no-delete triggers: true
    exactly when the row being changed belongs to a `published` graph
    version."""
    if table == "canonical_graph_versions":
        return "OLD.status = 'published'"
    return (
        "(SELECT status FROM canonical_graph_versions "
        "WHERE id = OLD.graph_version_id) = 'published'"
    )


def _insert_trigger_when(table: str) -> str:
    """The `WHEN` guard for `table`'s no-insert-replace trigger: true
    exactly when this INSERT conflicts (by primary key) with an existing
    row belonging to a `published` graph version."""
    if table == "canonical_graph_versions":
        return "EXISTS (SELECT 1 FROM canonical_graph_versions WHERE id = NEW.id AND status = 'published')"
    if table == "topics":
        return (
            "EXISTS (SELECT 1 FROM topics WHERE graph_version_id = NEW.graph_version_id "
            "AND stable_id = NEW.stable_id AND (SELECT status FROM canonical_graph_versions "
            "WHERE id = topics.graph_version_id) = 'published')"
        )
    return (
        f"EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id "
        f"AND (SELECT status FROM canonical_graph_versions "
        f"WHERE id = {table}.graph_version_id) = 'published')"
    )


def _create_immutability_triggers() -> None:
    for table, no_update_name, no_delete_name, no_insert_replace_name in _CONDITIONAL_APPROVED_TRIGGERS:
        when = _trigger_when(table)
        op.execute(
            f"""
            CREATE TRIGGER {no_update_name}
            BEFORE UPDATE ON {table}
            WHEN {when}
            BEGIN
                SELECT RAISE(ABORT, '{table} row belongs to a published canonical graph version: UPDATE is not permitted');
            END;
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {no_delete_name}
            BEFORE DELETE ON {table}
            WHEN {when}
            BEGIN
                SELECT RAISE(ABORT, '{table} row belongs to a published canonical graph version: DELETE is not permitted');
            END;
            """
        )
        insert_when = _insert_trigger_when(table)
        op.execute(
            f"""
            CREATE TRIGGER {no_insert_replace_name}
            BEFORE INSERT ON {table}
            WHEN {insert_when}
            BEGIN
                SELECT RAISE(ABORT, '{table} row belongs to a published canonical graph version: INSERT that overwrites an existing row is not permitted');
            END;
            """
        )


def _drop_immutability_triggers() -> None:
    for table, no_update_name, no_delete_name, no_insert_replace_name in reversed(_CONDITIONAL_APPROVED_TRIGGERS):
        op.execute(f"DROP TRIGGER {no_insert_replace_name}")
        op.execute(f"DROP TRIGGER {no_delete_name}")
        op.execute(f"DROP TRIGGER {no_update_name}")


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('topic_identities',
    sa.Column('stable_id', sa.Text(), nullable=False),
    sa.Column('stable_slug', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Text(), nullable=False),
    sa.Column('retired_at', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('stable_id', name=op.f('pk_topic_identities')),
    sa.UniqueConstraint('stable_slug', name=op.f('uq_topic_identities_stable_slug'))
    )
    op.create_table('canonical_graph_versions',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('version_label', sa.Text(), nullable=False),
    sa.Column('manifest_version', sa.Text(), nullable=False),
    sa.Column('manifest_hash', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('creator_owner_id', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Text(), nullable=False),
    sa.Column('published_at', sa.Text(), nullable=True),
    sa.Column('supersedes_version_id', sa.Text(), nullable=True),
    sa.CheckConstraint("status IN ('authored','curated','ai_draft','validation_failed','pending_approval','published')", name=op.f('ck_canonical_graph_versions_status_valid')),
    sa.ForeignKeyConstraint(['creator_owner_id'], ['owners.id'], name=op.f('fk_canonical_graph_versions_creator_owner_id_owners')),
    sa.ForeignKeyConstraint(['supersedes_version_id'], ['canonical_graph_versions.id'], name=op.f('fk_canonical_graph_versions_supersedes_version_id_canonical_graph_versions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_canonical_graph_versions')),
    sa.UniqueConstraint('manifest_hash', name=op.f('uq_canonical_graph_versions_manifest_hash')),
    sa.UniqueConstraint('version_label', name=op.f('uq_canonical_graph_versions_version_label'))
    )
    op.create_table('editorial_approvals',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('graph_version_id', sa.Text(), nullable=False),
    sa.Column('approver_owner_id', sa.Text(), nullable=False),
    sa.Column('approver_role', sa.Text(), nullable=False),
    sa.Column('basis_ref', sa.Text(), nullable=False),
    sa.Column('approved_at', sa.Text(), nullable=False),
    sa.CheckConstraint("approver_role IN ('designated_editorial_approver')", name=op.f('ck_editorial_approvals_approver_role_valid')),
    sa.ForeignKeyConstraint(['approver_owner_id'], ['owners.id'], name=op.f('fk_editorial_approvals_approver_owner_id_owners')),
    sa.ForeignKeyConstraint(['graph_version_id'], ['canonical_graph_versions.id'], name=op.f('fk_editorial_approvals_graph_version_id_canonical_graph_versions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_editorial_approvals')),
    sa.UniqueConstraint('graph_version_id', name=op.f('uq_editorial_approvals_graph_version_id'))
    )
    op.create_table('topics',
    sa.Column('graph_version_id', sa.Text(), nullable=False),
    sa.Column('stable_id', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('subject', sa.Text(), nullable=False),
    sa.Column('scope_tags', sa.Text(), nullable=False),
    sa.Column('level_tag', sa.Text(), nullable=False),
    sa.Column('target_capability', sa.Text(), nullable=False),
    sa.Column('recommended_layer', sa.Text(), nullable=False),
    sa.Column('checkpoint_start', sa.Integer(), nullable=False),
    sa.Column('checkpoint_end', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['graph_version_id'], ['canonical_graph_versions.id'], name=op.f('fk_topics_graph_version_id_canonical_graph_versions')),
    sa.ForeignKeyConstraint(['stable_id'], ['topic_identities.stable_id'], name='fk_topics_stable_id_topic_identities'),
    sa.PrimaryKeyConstraint('graph_version_id', 'stable_id', name=op.f('pk_topics'))
    )
    with op.batch_alter_table('topics', schema=None) as batch_op:
        batch_op.create_index('ix_topics_graph_version_subject', ['graph_version_id', 'subject'], unique=False)

    op.create_table('content_revisions',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('graph_version_id', sa.Text(), nullable=False),
    sa.Column('topic_stable_id', sa.Text(), nullable=False),
    sa.Column('layer', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('markdown_ref', sa.Text(), nullable=False),
    sa.Column('markdown_hash', sa.Text(), nullable=False),
    sa.Column('prompt_template_version', sa.Text(), nullable=True),
    sa.Column('creator_owner_id', sa.Text(), nullable=False),
    sa.Column('supersedes_revision_id', sa.Text(), nullable=True),
    sa.Column('created_at', sa.Text(), nullable=False),
    sa.CheckConstraint("status IN ('published')", name=op.f('ck_content_revisions_status_valid')),
    sa.CheckConstraint('length(trim(kind)) > 0', name=op.f('ck_content_revisions_kind_non_blank')),
    sa.ForeignKeyConstraint(['creator_owner_id'], ['owners.id'], name=op.f('fk_content_revisions_creator_owner_id_owners')),
    sa.ForeignKeyConstraint(['graph_version_id', 'topic_stable_id'], ['topics.graph_version_id', 'topics.stable_id'], name='fk_content_revisions_topics'),
    sa.ForeignKeyConstraint(['graph_version_id'], ['canonical_graph_versions.id'], name=op.f('fk_content_revisions_graph_version_id_canonical_graph_versions')),
    sa.ForeignKeyConstraint(['supersedes_revision_id'], ['content_revisions.id'], name=op.f('fk_content_revisions_supersedes_revision_id_content_revisions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_content_revisions')),
    sa.UniqueConstraint('graph_version_id', 'topic_stable_id', 'layer', 'markdown_hash', name='uq_content_revision_hash')
    )
    op.create_table('topic_relations',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('graph_version_id', sa.Text(), nullable=False),
    sa.Column('from_stable_id', sa.Text(), nullable=False),
    sa.Column('to_stable_id', sa.Text(), nullable=False),
    sa.Column('relation_type', sa.Text(), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=True),
    sa.CheckConstraint("relation_type IN ('prerequisite','scenario','related')", name=op.f('ck_topic_relations_relation_type_valid')),
    sa.ForeignKeyConstraint(['graph_version_id', 'from_stable_id'], ['topics.graph_version_id', 'topics.stable_id'], name='fk_topic_relations_from_topics'),
    sa.ForeignKeyConstraint(['graph_version_id', 'to_stable_id'], ['topics.graph_version_id', 'topics.stable_id'], name='fk_topic_relations_to_topics'),
    sa.ForeignKeyConstraint(['graph_version_id'], ['canonical_graph_versions.id'], name=op.f('fk_topic_relations_graph_version_id_canonical_graph_versions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_topic_relations')),
    sa.UniqueConstraint('graph_version_id', 'from_stable_id', 'to_stable_id', 'relation_type', name='uq_topic_relation_tuple')
    )
    # ### end Alembic commands ###

    _create_immutability_triggers()


def downgrade() -> None:
    """Downgrade schema."""
    _drop_immutability_triggers()

    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('topic_relations')
    op.drop_table('content_revisions')
    with op.batch_alter_table('topics', schema=None) as batch_op:
        batch_op.drop_index('ix_topics_graph_version_subject')

    op.drop_table('topics')
    op.drop_table('editorial_approvals')
    op.drop_table('canonical_graph_versions')
    op.drop_table('topic_identities')
    # ### end Alembic commands ###

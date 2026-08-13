"""Database-enforced import ownership and original immutability."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError


def test_import_foreign_keys_keep_optional_goal_and_duplicate_owner_consistent(
    engine: Engine,
):
    inspector = inspect(engine)
    record_fks = inspector.get_foreign_keys("import_records")
    assert any(
        fk["constrained_columns"] == ["goal_id", "owner_id"]
        and fk["referred_table"] == "goal_workspaces"
        for fk in record_fks
    )
    statement_fks = inspector.get_foreign_keys("import_statements")
    assert any(
        fk["constrained_columns"] == ["duplicate_of_statement_id", "owner_id"]
        and fk["referred_table"] == "import_statements"
        and fk["referred_columns"] == ["id", "owner_id"]
        for fk in statement_fks
    )


def test_exact_original_blob_and_hash_are_immutable_in_sqlite(engine: Engine):
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO owners (id,kind,display_name,status,created_at) VALUES (?,?,?,?,?)",
            (
                "owner-import-trigger",
                "local_builtin",
                "Owner",
                "active",
                "2026-08-12T00:00:00Z",
            ),
        )
        connection.exec_driver_sql(
            "INSERT INTO import_records "
            "(id,owner_id,goal_id,type,original_hash,parser_version,status,row_version,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                "import-trigger",
                "owner-import-trigger",
                None,
                "plain_text",
                "original-sha",
                "imports-v1",
                "selected",
                1,
                "2026-08-12T00:00:00Z",
                "2026-08-12T00:00:00Z",
            ),
        )
        connection.exec_driver_sql(
            "INSERT INTO import_record_bodies "
            "(import_id,owner_id,original_content) VALUES (?,?,?)",
            (
                "import-trigger",
                "owner-import-trigger",
                b"\xef\xbb\xbfexact\r\nbytes",
            ),
        )
        connection.exec_driver_sql(
            "UPDATE import_records SET status='parsing', row_version=2 WHERE id='import-trigger'"
        )
        with pytest.raises(IntegrityError, match="import original is immutable"):
            connection.exec_driver_sql(
                "UPDATE import_record_bodies SET original_content=? "
                "WHERE import_id='import-trigger'",
                (b"changed",),
            )
        with pytest.raises(IntegrityError, match="DELETE is not permitted"):
            connection.exec_driver_sql(
                "DELETE FROM import_records WHERE id='import-trigger'"
            )

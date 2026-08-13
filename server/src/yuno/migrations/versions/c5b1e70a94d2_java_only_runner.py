"""Java-only runner language constraint (IDK-406 under approved IDK-008).

`database-exercise-posture-v1` approves *absence* of any executable database
capability, not a connector seam. The `relational` language value never named
an implemented runner: it was produced by a configured-string branch that
reported `supported` without opening a connection or running a probe. It is
removed here rather than preserved behind a compatibility path.

`python` goes with it: approved IDK-005 records learner Python execution as
"None in MVP", so `direct-jdk-v1` Java is the only language the runner can
persist.

Disposal is bounded and is the *only* approved obsolete-row removal in this
chain -- not a general data-loss exception. It deletes, in one transaction:

  * `language='relational'` confirmations and runner records, plus any record
    whose confirmation is one of those placeholders;
  * their exclusively owned inputs, bodies, and output chunks;
  * the `kind='java_runner'` jobs whose logical request/run/result/confirmation
    references target those placeholders, with their attempts, events, results,
    and bodies.

Unrelated jobs and every goal, artifact, and evidence row survive, and the
migration proves no surviving logical reference points at a removed id before
rebuilding the checks.

`language='python'` rows are *not* covered by that approval. If any exist the
migration stops with a diagnostic rather than silently widening the approved
disposal to cover them.

This revision is forward-only: the deleted placeholder rows are not archived,
so there is nothing for a downgrade to restore.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c5b1e70a94d2"
down_revision: str | None = "f06c40340400"
branch_labels: str | None = None
depends_on: str | None = None


def _ids(connection: sa.Connection, statement: str) -> list[str]:
    return list(connection.execute(sa.text(statement)).scalars())


def _child_ids(
    connection: sa.Connection, table: str, column: str, parents: list[str]
) -> list[str]:
    """Ids of `table` rows whose `column` is in `parents`.

    Empty in, empty out: SQLite rejects an empty `IN ()`, so the query is
    skipped rather than rendered.
    """
    if not parents:
        return []
    statement = sa.text(f"SELECT id FROM {table} WHERE {column} IN :ids").bindparams(
        sa.bindparam("ids", expanding=True)
    )
    return list(connection.execute(statement, {"ids": parents}).scalars())


def _delete_in(
    connection: sa.Connection, table: str, column: str, ids: list[str]
) -> None:
    """Delete `table` rows whose `column` is in `ids`, in one expanded statement."""
    if not ids:
        return
    statement = sa.text(f"DELETE FROM {table} WHERE {column} IN :ids").bindparams(
        sa.bindparam("ids", expanding=True)
    )
    connection.execute(statement, {"ids": ids})


def upgrade() -> None:
    connection = op.get_bind()

    stranded_python = _ids(
        connection,
        "SELECT id FROM runner_confirmations WHERE language = 'python' "
        "UNION SELECT id FROM runner_records WHERE language = 'python'",
    )
    if stranded_python:
        raise RuntimeError(
            "Cannot apply the Java-only runner constraint: "
            f"{len(stranded_python)} row(s) still record language='python'. "
            "IDK-008 approves deleting relational placeholder rows only, so "
            "this migration will not remove them. Inspect "
            "runner_confirmations/runner_records for language='python' and "
            "resolve them explicitly, then re-run `alembic upgrade head`."
        )

    confirmations = _ids(
        connection,
        "SELECT id FROM runner_confirmations WHERE language = 'relational'",
    )
    records = _ids(
        connection,
        "SELECT id FROM runner_records WHERE language = 'relational' "
        "UNION SELECT id FROM runner_records WHERE confirmation_id IN ("
        "SELECT id FROM runner_confirmations WHERE language = 'relational')",
    )

    request_refs = [f"RunnerRun:{record}" for record in records]

    jobs: list[str] = []
    if records or confirmations:
        statement = sa.text(
            "SELECT id FROM jobs WHERE kind = 'java_runner' AND ("
            "  id IN :records"
            "  OR run_id IN :records"
            "  OR result_ref IN :records"
            "  OR request_ref IN :request_refs"
            "  OR confirmation_ref IN :confirmations)"
        ).bindparams(
            sa.bindparam("records", expanding=True),
            sa.bindparam("request_refs", expanding=True),
            sa.bindparam("confirmations", expanding=True),
        )
        jobs = list(
            connection.execute(
                statement,
                {
                    # An empty `IN ()` is a SQLite syntax error, and these three
                    # sets are independently empty -- a placeholder confirmation
                    # that never reached a run leaves `records` empty. A sentinel
                    # that cannot collide with a generated id keeps the predicate
                    # well-formed and false.
                    "records": records or ["\x00"],
                    "request_refs": request_refs or ["\x00"],
                    "confirmations": confirmations or ["\x00"],
                },
            ).scalars()
        )

    # Runner record subgraph, leaves first: bodies hang off inputs and chunks,
    # which hang off the record.
    chunks = _child_ids(connection, "runner_output_chunks", "runner_id", records)
    run_inputs = _child_ids(connection, "runner_inputs", "runner_id", records)

    _delete_in(connection, "runner_output_chunk_bodies", "chunk_id", chunks)
    _delete_in(connection, "runner_output_chunks", "runner_id", records)
    _delete_in(connection, "runner_input_bodies", "input_id", run_inputs)
    _delete_in(connection, "runner_inputs", "runner_id", records)
    _delete_in(connection, "runner_record_bodies", "runner_id", records)
    _delete_in(connection, "runner_records", "id", records)

    # Confirmation subgraph.
    confirmation_inputs = _child_ids(
        connection, "runner_confirmation_inputs", "confirmation_id", confirmations
    )
    _delete_in(
        connection, "runner_confirmation_input_bodies", "input_id", confirmation_inputs
    )
    _delete_in(
        connection, "runner_confirmation_inputs", "confirmation_id", confirmations
    )
    _delete_in(connection, "runner_confirmations", "id", confirmations)

    # Operational job subgraph owned by those placeholders. `job_result_bodies`
    # and `job_attempt_bodies` key on the result/attempt id, not the job id, so
    # those ids are resolved before their parents go.
    results = _child_ids(connection, "job_results", "job_id", jobs)
    attempts = _child_ids(connection, "job_attempts", "job_id", jobs)

    _delete_in(connection, "job_result_bodies", "result_id", results)
    _delete_in(connection, "job_results", "job_id", jobs)
    _delete_in(connection, "job_attempt_bodies", "attempt_id", attempts)
    _delete_in(connection, "job_attempts", "job_id", jobs)
    _delete_in(connection, "job_events", "job_id", jobs)
    _delete_in(connection, "job_bodies", "job_id", jobs)
    _delete_in(connection, "jobs", "id", jobs)

    _assert_no_dangling_references(connection, records, confirmations, request_refs)

    for table in ("runner_confirmations", "runner_records"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint("language_valid", type_="check")
            batch.create_check_constraint("language_valid", "language IN ('java')")


def _assert_no_dangling_references(
    connection: sa.Connection,
    records: list[str],
    confirmations: list[str],
    request_refs: list[str],
) -> None:
    """Fail the migration if any surviving row still points at a removed id.

    `runner_records.job_id`, `jobs.run_id`, `jobs.request_ref`,
    `jobs.result_ref`, and `jobs.confirmation_ref` are typed logical
    references carried as plain text, not foreign keys, so nothing but this
    check proves the disposal was complete. `request_refs` is threaded in
    from `upgrade()` rather than rederived, since it is already computed
    there for the job-selection query.
    """
    if not records and not confirmations:
        return

    removed = {*records, *confirmations}
    request_ref_set = set(request_refs)
    survivors: list[str] = []

    rows = connection.execute(
        sa.text(
            "SELECT id, run_id, request_ref, result_ref, confirmation_ref FROM jobs"
        )
    ).all()
    for job_id, run_id, request_ref, result_ref, confirmation_ref in rows:
        for label, value in (
            ("run_id", run_id),
            ("result_ref", result_ref),
            ("confirmation_ref", confirmation_ref),
        ):
            if value is not None and value in removed:
                survivors.append(f"jobs.{label}={value!r} on job {job_id!r}")
        if request_ref is not None and request_ref in request_ref_set:
            survivors.append(f"jobs.request_ref={request_ref!r} on job {job_id!r}")

    runner_rows = connection.execute(
        sa.text("SELECT id, job_id, confirmation_id FROM runner_records")
    ).all()
    for runner_id, job_id, confirmation_id in runner_rows:
        if confirmation_id in removed:
            survivors.append(
                f"runner_records.confirmation_id={confirmation_id!r} "
                f"on record {runner_id!r}"
            )
        if job_id in removed:
            survivors.append(
                f"runner_records.job_id={job_id!r} on record {runner_id!r}"
            )

    if survivors:
        raise RuntimeError(
            "Java-only runner disposal left dangling logical references: "
            + "; ".join(sorted(survivors))
        )


def downgrade() -> None:
    raise NotImplementedError(
        "The Java-only runner constraint is forward-only: the relational and "
        "python language values were removed under approved IDK-005/IDK-008, "
        "and the placeholder rows deleted with them are not archived."
    )

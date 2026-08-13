from __future__ import annotations

from sqlalchemy import Engine, text

from yuno.modules.data_lifecycle.domain import (
    CleanupIntent,
    CleanupIntentKind,
    CleanupIntentStatus,
)
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.ids import new_id


def _owner(engine: Engine) -> str:
    owner_id = new_id()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO owners(id,kind,display_name,status,created_at) VALUES (:id,'local_builtin','Owner','active',:at)"
            ),
            {"id": owner_id, "at": "2026-01-01T00:00:00+00:00"},
        )
    return owner_id


def _job(
    connection,
    owner_id: str,
    job_id: str,
    *,
    state: str,
    terminal_at: str | None,
    result: bool,
) -> None:
    connection.execute(
        text(
            "INSERT INTO jobs(id,owner_id,kind,schema_version,lane,state,retryable,payload_hash,correlation_id,request_id,attempt,priority,queued_at,terminal_at,updated_at) VALUES (:id,:owner,'test','1','background',:state,0,:hash,'correlation','request',1,100,'2026-01-01T00:00:00.000000Z',:terminal,:updated)"
        ),
        {
            "id": job_id,
            "owner": owner_id,
            "state": state,
            "hash": "a" * 64,
            "terminal": terminal_at,
            "updated": terminal_at or "2026-01-01T00:00:00.000000Z",
        },
    )
    connection.execute(
        text(
            "INSERT INTO job_bodies(job_id,owner_id,payload_json,diagnostic) VALUES (:id,:owner,'{}','private diagnostic')"
        ),
        {"id": job_id, "owner": owner_id},
    )
    connection.execute(
        text(
            "INSERT INTO job_attempts(id,owner_id,job_id,attempt_number,started_at,ended_at,outcome) VALUES (:attempt,:owner,:id,1,'2026-01-01T00:00:00.000000Z',:terminal,:state)"
        ),
        {
            "attempt": f"attempt-{job_id}",
            "owner": owner_id,
            "id": job_id,
            "terminal": terminal_at,
            "state": "succeeded" if state == "succeeded" else "failed",
        },
    )
    connection.execute(
        text(
            "INSERT INTO job_attempt_bodies(attempt_id,owner_id,diagnostic) VALUES (:attempt,:owner,'private attempt')"
        ),
        {"attempt": f"attempt-{job_id}", "owner": owner_id},
    )
    if result:
        connection.execute(
            text(
                "INSERT INTO job_results(id,owner_id,job_id,kind,schema_version,result_ref,result_hash,committed_at) VALUES (:result,:owner,:id,'test','1',:ref,:hash,:terminal)"
            ),
            {
                "result": f"result-{job_id}",
                "owner": owner_id,
                "id": job_id,
                "ref": f"Result:{job_id}",
                "hash": "b" * 64,
                "terminal": terminal_at,
            },
        )
        connection.execute(
            text(
                "INSERT INTO job_result_bodies(result_id,owner_id,warnings_json) VALUES (:result,:owner,'[]')"
            ),
            {"result": f"result-{job_id}", "owner": owner_id},
        )


def test_export_package_expiry_is_owner_scoped_and_preserves_expired_metadata(
    engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner(engine)
    with engine.begin() as connection:
        for operation_id, expires in (
            ("mine", "2026-01-02T00:00:00+00:00"),
            ("newer", "2026-01-04T00:00:00+00:00"),
        ):
            connection.execute(
                text(
                    "INSERT INTO export_operations(id,owner_id,status,format_version,package_expires_at,metadata_expires_at,created_at,updated_at) VALUES (:id,:owner,'complete','1.0',:expires,'2026-02-01T00:00:00+00:00','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')"
                ),
                {"id": operation_id, "owner": owner_id, "expires": expires},
            )
            connection.execute(
                text(
                    "INSERT INTO export_package_bodies(operation_id,owner_id,package_json) VALUES (:id,:owner,'{}')"
                ),
                {"id": operation_id, "owner": owner_id},
            )
    with uow_factory() as uow:
        assert (
            uow.data_lifecycle.expire_export_packages(
                owner_id, "2026-01-03T00:00:00+00:00"
            )
            == 1
        )
        uow.commit()
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM export_package_bodies WHERE operation_id='mine'"
                )
            )
            == 0
        )
        assert (
            connection.scalar(
                text("SELECT status FROM export_operations WHERE id='mine'")
            )
            == "expired"
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM export_package_bodies WHERE operation_id='newer'"
                )
            )
            == 1
        )


def test_file_cleanup_intent_is_durable_retryable_and_owner_scoped(
    engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner(engine)
    intent = CleanupIntent(
        new_id(),
        owner_id,
        None,
        CleanupIntentKind.RUNNER_WORKSPACE,
        "runner/workspace/ref",
        "a" * 64,
        CleanupIntentStatus.PENDING,
        None,
        0,
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:00+00:00",
        None,
    )
    with uow_factory() as uow:
        uow.data_lifecycle.add_cleanup_intent(intent)
        uow.commit()
    with uow_factory() as uow:
        assert uow.data_lifecycle.fail_cleanup_intent(
            owner_id, intent.id, "permission-denied", "2026-01-01T00:01:00+00:00"
        )
        uow.commit()
    with uow_factory() as uow:
        pending = uow.data_lifecycle.list_pending_cleanup_intents(owner_id)
        assert pending[0].status is CleanupIntentStatus.FAILED
        assert pending[0].attempts == 1
        assert uow.data_lifecycle.finish_cleanup_intent(
            owner_id, intent.id, "2026-01-01T00:02:00+00:00"
        )
        uow.commit()


def test_terminal_job_exhaust_waits_for_reconciliation_and_keeps_job_header(
    engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner(engine)
    with engine.begin() as connection:
        _job(
            connection,
            owner_id,
            "old-reconciled",
            state="succeeded",
            terminal_at="2026-01-01T00:00:00.000000Z",
            result=True,
        )
        _job(
            connection,
            owner_id,
            "old-unreconciled",
            state="succeeded",
            terminal_at="2026-01-01T00:00:00.000000Z",
            result=False,
        )
        _job(
            connection,
            owner_id,
            "new-reconciled",
            state="succeeded",
            terminal_at="2026-02-01T00:00:00.000000Z",
            result=True,
        )
    with uow_factory() as uow:
        assert (
            uow.data_lifecycle.purge_job_exhaust(
                owner_id, "2026-01-15T00:00:00.000000Z"
            )
            == 1
        )
        uow.commit()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM jobs")) == 3
        assert (
            connection.scalar(
                text("SELECT count(*) FROM job_bodies WHERE job_id='old-reconciled'")
            )
            == 0
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM job_attempts WHERE job_id='old-reconciled'")
            )
            == 0
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM job_results WHERE job_id='old-reconciled'")
            )
            == 0
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM job_bodies WHERE job_id='old-unreconciled'")
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM job_bodies WHERE job_id='new-reconciled'")
            )
            == 1
        )


def test_job_event_expiry_applies_age_and_owner_cap_only_to_terminal_jobs(
    engine: Engine, uow_factory: UnitOfWorkFactory
) -> None:
    owner_id = _owner(engine)
    with engine.begin() as connection:
        _job(
            connection,
            owner_id,
            "terminal",
            state="failed",
            terminal_at="2026-01-01T00:00:00.000000Z",
            result=False,
        )
        _job(
            connection,
            owner_id,
            "active",
            state="running",
            terminal_at=None,
            result=False,
        )
        for job_id, created_at in (
            ("terminal", "2026-01-01T00:00:00.000000Z"),
            ("terminal", "2026-02-01T00:00:00.000000Z"),
            ("active", "2026-01-01T00:00:00.000000Z"),
            ("terminal", "2026-02-02T00:00:00.000000Z"),
        ):
            connection.execute(
                text(
                    "INSERT INTO job_events(owner_id,job_id,type,state,retryable,correlation_id,request_id,created_at) VALUES (:owner,:job,'state',:state,0,'correlation','request',:created)"
                ),
                {
                    "owner": owner_id,
                    "job": job_id,
                    "state": "running" if job_id == "active" else "failed",
                    "created": created_at,
                },
            )
    with uow_factory() as uow:
        assert (
            uow.data_lifecycle.expire_job_events(
                owner_id, "2026-01-15T00:00:00.000000Z", 2
            )
            == 2
        )
        uow.commit()
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM job_events WHERE job_id='active'")
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM job_events WHERE job_id='terminal'")
            )
            == 1
        )

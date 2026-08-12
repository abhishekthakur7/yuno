from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from yuno.modules.runner.models import (
    RunnerConfirmationInputRow,
    RunnerConfirmationRow,
    RunnerInputRow,
    RunnerOutputChunkRow,
    RunnerRecordRow,
)


class RunnerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def confirmation(self, owner_id: str, confirmation_id: str):
        return self.session.scalars(
            select(RunnerConfirmationRow).where(
                RunnerConfirmationRow.owner_id == owner_id,
                RunnerConfirmationRow.id == confirmation_id,
            )
        ).one_or_none()

    def confirmation_by_idempotency(self, owner_id: str, key: str):
        return self.session.scalars(
            select(RunnerConfirmationRow).where(
                RunnerConfirmationRow.owner_id == owner_id,
                RunnerConfirmationRow.idempotency_key == key,
            )
        ).one_or_none()

    def reserve_confirmation(
        self,
        owner_id: str,
        confirmation_id: str,
        *,
        key: str,
        request_hash: str,
        run_id: str,
        consumed_at: str,
    ) -> bool:
        result = self.session.execute(
            update(RunnerConfirmationRow)
            .where(
                RunnerConfirmationRow.owner_id == owner_id,
                RunnerConfirmationRow.id == confirmation_id,
                RunnerConfirmationRow.consumed_at.is_(None),
                RunnerConfirmationRow.idempotency_key.is_(None),
            )
            .values(
                consumed_at=consumed_at,
                idempotency_key=key,
                request_hash=request_hash,
                reserved_run_id=run_id,
            )
        )
        self.session.flush()
        return result.rowcount == 1

    def record(self, owner_id: str, run_id: str):
        return self.session.scalars(
            select(RunnerRecordRow).where(
                RunnerRecordRow.owner_id == owner_id, RunnerRecordRow.id == run_id
            )
        ).one_or_none()

    def confirmation_inputs(self, owner_id: str, confirmation_id: str):
        return tuple(
            self.session.scalars(
                select(RunnerConfirmationInputRow)
                .where(
                    RunnerConfirmationInputRow.owner_id == owner_id,
                    RunnerConfirmationInputRow.confirmation_id == confirmation_id,
                )
                .order_by(RunnerConfirmationInputRow.logical_path)
            ).all()
        )

    def inputs(self, owner_id: str, run_id: str):
        return tuple(
            self.session.scalars(
                select(RunnerInputRow)
                .where(
                    RunnerInputRow.owner_id == owner_id,
                    RunnerInputRow.runner_id == run_id,
                )
                .order_by(RunnerInputRow.logical_path)
            ).all()
        )

    def chunks(self, owner_id: str, run_id: str):
        return tuple(
            self.session.scalars(
                select(RunnerOutputChunkRow)
                .where(
                    RunnerOutputChunkRow.owner_id == owner_id,
                    RunnerOutputChunkRow.runner_id == run_id,
                )
                .order_by(RunnerOutputChunkRow.ordinal)
            ).all()
        )

    def pending_dispatch_records(self):
        return tuple(
            self.session.scalars(
                select(RunnerRecordRow)
                .where(RunnerRecordRow.state == "queued")
                .order_by(RunnerRecordRow.created_at)
            ).all()
        )

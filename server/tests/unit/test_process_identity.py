from __future__ import annotations

from yuno.modules.jobs_events import service as job_service
from yuno.modules.provider import adapters
from yuno.shared.infrastructure.processes import process_identity


def test_provider_and_job_reconciliation_share_process_identity() -> None:
    assert adapters.process_identity is process_identity
    assert job_service.process_identity is process_identity
    assert process_identity(999_999).endswith(":unavailable")

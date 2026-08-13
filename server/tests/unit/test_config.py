from __future__ import annotations

import pytest
from pydantic import ValidationError

from yuno.config import MIB, Settings


def test_idk_010_policy_values_are_typed_and_fixed() -> None:
    settings = Settings()

    assert settings.data_lifecycle_policy_version == "1.0"
    assert settings.import_original_max_bytes == 10 * MIB
    assert settings.evidence_payload_max_bytes == 10 * MIB
    assert settings.generated_body_max_bytes == 2 * MIB
    assert settings.runner_output_bytes == 2 * MIB
    assert settings.runner_temp_bytes == 256 * MIB
    assert settings.job_janitor_retention_seconds == 3600
    assert settings.export_format == "yuno-portable-export"
    assert settings.export_format_version == "1.0"
    assert settings.export_privacy_review_approved is False
    assert settings.export_package_retention_seconds == 86_400
    assert settings.export_operation_retention_days == 30
    assert settings.structured_log_file_count == 5
    assert settings.structured_log_total_max_bytes == 50 * MIB


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("import_original_max_bytes", 10 * MIB - 1),
        ("overlay_proposal_pending_cap", 24),
        ("pending_job_cap", 101),
        ("runner_workspace_retention_seconds", 86_400),
        ("export_format_version", "2.0"),
        ("structured_log_retention_days", 15),
    ],
)
def test_idk_010_policy_values_cannot_be_weakened_or_reinterpreted(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_idk_010_policy_values_validate_on_assignment() -> None:
    settings = Settings()

    with pytest.raises(ValidationError):
        settings.export_format_version = "test-export-v1"  # type: ignore[assignment]

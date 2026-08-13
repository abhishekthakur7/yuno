"""Runtime settings.

Neither domain nor application — `yuno.config` sits above them and is
imported by infrastructure/API code, so depending on `pydantic-settings`
here is fine (the framework-free rule applies only to `yuno.shared.domain`/
`yuno.shared.application` and each module's `domain.py`/`ports.py`/
`service.py`).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MIB = 1024 * 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YUNO_", validate_assignment=True)

    database_url: str = "sqlite+pysqlite:///./yuno.db"
    owner_display_name: str = "Local owner"
    data_lifecycle_policy_version: Literal["1.0"] = "1.0"

    import_original_max_bytes: Literal[10 * MIB] = 10 * MIB
    import_retained_owner_limit: Literal[100] = 100
    import_statements_per_import_limit: Literal[10_000] = 10_000
    import_unreviewed_owner_limit: Literal[50_000] = 50_000
    evidence_payload_max_bytes: Literal[10 * MIB] = 10 * MIB
    evidence_retained_owner_limit: Literal[10_000] = 10_000
    generated_body_max_bytes: Literal[2 * MIB] = 2 * MIB
    generated_retained_owner_limit: Literal[5_000] = 5_000
    interview_turns_per_session_limit: Literal[1_000] = 1_000
    interview_bytes_per_session_limit: Literal[10 * MIB] = 10 * MIB
    interview_sessions_owner_limit: Literal[200] = 200
    runner_input_files_limit: Literal[100] = 100
    runner_input_bytes_limit: Literal[10 * MIB] = 10 * MIB
    runner_stdout_bytes_limit: Literal[MIB] = MIB
    runner_stderr_bytes_limit: Literal[MIB] = MIB
    runner_output_bytes: Literal[2 * MIB] = 2 * MIB
    runner_temp_bytes: Literal[256 * MIB] = 256 * MIB
    runner_temp_files_limit: Literal[10_000] = 10_000
    overlay_proposal_pending_cap: Literal[25] = 25
    pending_job_cap: Literal[100] = 100

    diagnostic_abandoned_retention_days: Literal[30] = 30
    interview_inactive_retention_days: Literal[30] = 30
    terminal_job_retention_days: Literal[30] = 30
    job_event_retention_days: Literal[7] = 7
    job_event_owner_limit: Literal[10_000] = 10_000
    runner_output_retention_days: Literal[7] = 7
    runner_workspace_retention_seconds: Literal[3600] = 3600
    export_package_retention_seconds: Literal[86_400] = 86_400
    export_operation_retention_days: Literal[30] = 30
    structured_log_file_count: Literal[5] = 5
    structured_log_file_max_bytes: Literal[10 * MIB] = 10 * MIB
    structured_log_total_max_bytes: Literal[50 * MIB] = 50 * MIB
    structured_log_retention_days: Literal[14] = 14

    background_job_age_promotion_seconds: Literal[300] = 300
    job_janitor_retention_seconds: Literal[3600] = 3600
    provider_first_output_seconds: float | None = None
    provider_inactivity_seconds: float | None = None
    provider_absolute_seconds: float | None = None
    source_snapshot_root: Path = Path("./yuno-source-snapshots")
    provider_quarantine_root: Path = Field(
        default=Path.home()
        / "Library"
        / "Application Support"
        / "Yuno"
        / "provider-quarantine"
    )
    export_format: Literal["yuno-portable-export"] = "yuno-portable-export"
    export_format_version: Literal["1.0"] = "1.0"
    export_privacy_review_approved: bool = True
    structured_log_directory: Path = Field(
        default=Path.home() / "Library" / "Application Support" / "Yuno" / "logs"
    )
    # Execution is fail-closed until every policy value and approved command
    # name is supplied.
    runner_enabled: bool = False
    runner_environment_policy_version: str | None = None
    runner_limits_config_version: str | None = None
    runner_confirmation_ttl_seconds: int | None = None
    runner_wall_time_seconds: float | None = None
    runner_cpu_seconds: int | None = None
    runner_memory_bytes: int | None = None
    runner_process_limit: int | None = None
    runner_file_bytes: int | None = None
    runner_javac_command: str | None = None
    runner_java_command: str | None = None
    runner_java_version_prefix: str | None = None
    runner_python_command: str | None = None
    runner_relational_connector: Literal["configured"] | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

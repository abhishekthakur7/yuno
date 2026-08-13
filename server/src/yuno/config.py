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

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YUNO_")

    database_url: str = "sqlite+pysqlite:///./yuno.db"
    owner_display_name: str = "Local owner"
    overlay_proposal_pending_cap: int = 25
    pending_job_cap: int = 100
    background_job_age_promotion_seconds: int = 300
    job_janitor_retention_seconds: int = 86400
    provider_first_output_seconds: float | None = None
    provider_inactivity_seconds: float | None = None
    provider_absolute_seconds: float | None = None
    source_snapshot_root: Path = Path("./yuno-source-snapshots")
    export_format_version: str | None = None
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
    runner_output_bytes: int | None = None
    runner_file_bytes: int | None = None
    runner_temp_bytes: int | None = None
    runner_javac_command: str | None = None
    runner_java_command: str | None = None
    runner_java_version_prefix: str | None = None
    runner_python_command: str | None = None
    runner_relational_connector: Literal["configured"] | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

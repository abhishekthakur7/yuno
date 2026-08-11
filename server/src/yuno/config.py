"""Runtime settings.

Neither domain nor application — `yuno.config` sits above them and is
imported by infrastructure/API code, so depending on `pydantic-settings`
here is fine (the framework-free rule applies only to `yuno.shared.domain`/
`yuno.shared.application` and each module's `domain.py`/`ports.py`/
`service.py`).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YUNO_")

    database_url: str = "sqlite+pysqlite:///./yuno.db"
    owner_display_name: str = "Local owner"


@lru_cache
def get_settings() -> Settings:
    return Settings()

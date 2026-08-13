from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, TextIO

LOGGER_NAME = "yuno.observability"
LOG_FILENAME = "yuno.log"
REDACTED = "[REDACTED]"

_SENSITIVE_KEY_PARTS = (
    "auth_",
    "authorization",
    "body",
    "credential",
    "cookie",
    "display_name",
    "email",
    "exception",
    "ip_address",
    "password",
    "secret",
    "token",
    "user_agent",
    "api_key",
    "apikey",
    "access_key",
    "environment",
    "_env",
    "raw_prompt",
    "prompt_body",
    "transcript",
    "artifact_body",
    "raw_output",
    "quarantine_output",
)
_ABSOLUTE_PATH = re.compile(r"^(?:/|[A-Za-z]:[\\/])")
_SAFE_FIELDS = frozenset(
    {
        "request_id",
        "correlation_id",
        "owner_id",
        "goal_id",
        "job_id",
        "provider_request_id",
        "runner_id",
        "run_id",
        "method",
        "route",
        "status_code",
        "provider",
        "lifecycle",
        "diagnostic_classification",
    }
)


class _OwnerOnlyRotatingFileHandler(RotatingFileHandler):
    def __init__(
        self,
        filename: Path,
        *,
        max_bytes: int,
        backup_count: int,
        max_age: timedelta,
    ) -> None:
        self._max_age_seconds = max_age.total_seconds()
        super().__init__(
            filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        self._restrict_file_permissions()

    def _open(self) -> TextIO:
        stream = super()._open()
        os.chmod(self.baseFilename, 0o600)
        return stream

    def _restrict_file_permissions(self) -> None:
        for path in self._managed_paths():
            if path.is_file():
                os.chmod(path, 0o600)

    def _managed_paths(self) -> tuple[Path, ...]:
        active = Path(self.baseFilename)
        return (active,) + tuple(
            Path(f"{self.baseFilename}.{index}")
            for index in range(1, self.backupCount + 1)
        )

    def _remove_expired_files(self) -> None:
        cutoff = datetime.now(UTC).timestamp() - self._max_age_seconds
        active_path = Path(self.baseFilename)
        for path in self._managed_paths():
            try:
                expired = path.stat().st_mtime < cutoff
            except FileNotFoundError:
                continue
            if not expired:
                continue
            if path == active_path and self.stream is not None:
                self.stream.close()
                self.stream = None
            path.unlink(missing_ok=True)

    def expire(self) -> None:
        self.acquire()
        try:
            self._remove_expired_files()
        finally:
            self.release()

    def _encoded_record_size(self, record: logging.LogRecord) -> int:
        return len(f"{self.format(record)}{self.terminator}".encode())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._remove_expired_files()
            record_size = self._encoded_record_size(record)
            if record_size > self.maxBytes:
                return
            current_size = (
                Path(self.baseFilename).stat().st_size
                if Path(self.baseFilename).exists()
                else 0
            )
            if current_size and current_size + record_size > self.maxBytes:
                self.doRollover()
            logging.FileHandler.emit(self, record)
            self._restrict_file_permissions()
        except (OSError, UnicodeError, ValueError):
            self.handleError(record)


def _replace_handlers(logger: logging.Logger, handler: logging.Handler) -> None:
    for current in logger.handlers:
        current.close()
    logger.handlers.clear()
    handler.set_name(LOGGER_NAME)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def configure_structured_logging(stream: TextIO | None = None) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    _replace_handlers(logger, logging.StreamHandler(stream or sys.stderr))
    return logger


def configure_file_structured_logging(
    directory: Path,
    *,
    max_bytes: int,
    backup_count: int,
    max_age: timedelta,
) -> logging.Logger:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if backup_count <= 0:
        raise ValueError("backup_count must be positive")
    if max_age <= timedelta(0):
        raise ValueError("max_age must be positive")

    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    log_path = directory / LOG_FILENAME
    cutoff = datetime.now(UTC).timestamp() - max_age.total_seconds()
    for path in (log_path,) + tuple(
        Path(f"{log_path}.{index}") for index in range(1, backup_count + 1)
    ):
        try:
            expired = path.stat().st_mtime < cutoff
        except FileNotFoundError:
            continue
        if expired:
            path.unlink(missing_ok=True)

    handler = _OwnerOnlyRotatingFileHandler(
        log_path,
        max_bytes=max_bytes,
        backup_count=backup_count,
        max_age=max_age,
    )
    logger = logging.getLogger(LOGGER_NAME)
    _replace_handlers(logger, handler)
    return logger


def expire_structured_log_files(
    logger: logging.Logger | None = None,
) -> None:
    configured = logger or logging.getLogger(LOGGER_NAME)
    for handler in configured.handlers:
        if isinstance(handler, _OwnerOnlyRotatingFileHandler):
            handler.expire()


def redact_log_data(value: Any, *, key: str | None = None) -> Any:
    normalized_key = (key or "").lower().replace("-", "_")
    if normalized_key == "env" or (
        normalized_key and any(part in normalized_key for part in _SENSITIVE_KEY_PARTS)
    ):
        return REDACTED
    if normalized_key == "route" and isinstance(value, str) and "?" in value:
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_log_data(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_log_data(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return REDACTED
    if isinstance(value, str) and _ABSOLUTE_PATH.match(value):
        if normalized_key == "route" and value.startswith("/api/"):
            return value
        return REDACTED
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def log_event(
    event: str,
    *,
    level: int = logging.INFO,
    logger: logging.Logger | None = None,
    **fields: Any,
) -> None:
    safe_fields = {
        key: redact_log_data(value, key=key)
        for key, value in fields.items()
        if key in _SAFE_FIELDS and value is not None
    }
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": logging.getLevelName(level).lower(),
        "event": event,
        **safe_fields,
    }
    (logger or logging.getLogger(LOGGER_NAME)).log(
        level, json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )

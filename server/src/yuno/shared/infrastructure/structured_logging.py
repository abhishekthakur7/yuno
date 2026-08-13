from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, TextIO

LOGGER_NAME = "yuno.observability"
REDACTED = "[REDACTED]"

_SENSITIVE_KEY_PARTS = (
    "auth_",
    "authorization",
    "credential",
    "cookie",
    "password",
    "secret",
    "token",
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


def configure_structured_logging(stream: TextIO | None = None) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not any(handler.get_name() == LOGGER_NAME for handler in logger.handlers):
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.set_name(LOGGER_NAME)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def redact_log_data(value: Any, *, key: str | None = None) -> Any:
    normalized_key = (key or "").lower().replace("-", "_")
    if normalized_key == "env" or (
        normalized_key and any(part in normalized_key for part in _SENSITIVE_KEY_PARTS)
    ):
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

"""Clock abstraction and the canonical UTC TEXT timestamp format.

Every stored timestamp (spec §4.1: "Timestamps: UTC TEXT") is produced by
`utc_text`/`now_text` so the format is identical across every table and
module: ISO-8601, UTC, microsecond precision, e.g.
`2026-08-11T12:00:00.000000Z`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current timezone-aware UTC time."""
        ...


class SystemClock:
    """`Clock` backed by the system wall clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def utc_text(dt: datetime) -> str:
    """Render a timezone-aware datetime as the stored UTC TEXT timestamp.

    Raises `ValueError` if `dt` is naive — every timestamp we persist must
    carry explicit timezone information before formatting.
    """
    if dt.tzinfo is None:
        raise ValueError("utc_text requires a timezone-aware datetime")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def now_text(clock: Clock) -> str:
    """Return `clock`'s current time formatted as UTC TEXT."""
    return utc_text(clock.now())

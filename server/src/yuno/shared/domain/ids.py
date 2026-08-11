"""Opaque identifier generation (spec §4.1: opaque TEXT ULID ids).

`python-ulid` is the sole third-party import allowed anywhere in the
framework-free layer (`yuno.shared.domain`, `yuno.shared.application`, and
each module's `domain.py`/`ports.py`/`service.py`) — confined to this
module.
"""

from __future__ import annotations

from ulid import ULID


def new_id() -> str:
    """Return a new 26-character Crockford-base32 ULID string."""
    return str(ULID())

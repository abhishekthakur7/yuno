"""Canonical-JSON payload hashing.

Shared (not audit-owned) because it has no audit-specific meaning of its
own: `yuno.modules.audit`'s `AuditEvent.before_hash`/`after_hash` is one
caller, `yuno.shared.infrastructure.jobs.InProcessJobDispatcher`'s
payload-identity check is another, and future modules may reuse it the
same way (spec §8.5 forbids avoidable sensitive payloads in audit -- this
is how a caller records "what changed" without storing the payload body
itself).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_payload(value: Any) -> str:
    """Return a stable SHA-256 hex digest of `value`'s canonical JSON form.

    Canonical here means: keys sorted, no extraneous whitespace. Suitable
    for recording "before/after" identity (e.g. `AuditEvent.before_hash`/
    `after_hash`), never for storing the payload itself.
    """
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

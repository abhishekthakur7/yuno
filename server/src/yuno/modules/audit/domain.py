"""Append-only audit event contract (spec §4.7's `audit_events` row).

Callers record before/after *hashes* rather than raw payload bodies --
spec §8.5 forbids avoidable sensitive payloads in audit -- via
`yuno.shared.domain.hashing.hash_payload`.

Framework-free (spec §3.2) -- see `yuno.shared.domain`'s docstring for the
rule this module is bound by.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEvent:
    id: str
    owner_id: str
    goal_id: str | None
    actor_role: str
    entity_type: str
    entity_id: str
    action: str
    before_hash: str | None
    after_hash: str | None
    reason: str | None
    request_id: str | None
    correlation_id: str | None
    occurred_at: str

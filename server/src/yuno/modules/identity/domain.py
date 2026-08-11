"""Owner identity, roles and role policy (spec §4.2).

There is exactly one built-in local owner in MVP (`OwnerKind.LOCAL_BUILTIN`),
resolved server-side on every request. Learner and editorial-approver roles
are independently granted and must stay distinct (spec §4.2, D1).

Framework-free (spec §3.2) -- see `yuno.shared.domain`'s docstring for the
rule this module is bound by.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from yuno.shared.domain.errors import RoleNotGrantedError


class OwnerKind(StrEnum):
    LOCAL_BUILTIN = "local_builtin"


class OwnerStatus(StrEnum):
    ACTIVE = "active"
    TOMBSTONED = "tombstoned"


class Role(StrEnum):
    LEARNER = "learner"
    DESIGNATED_EDITORIAL_APPROVER = "designated_editorial_approver"


@dataclass(frozen=True)
class Owner:
    id: str
    kind: OwnerKind
    display_name: str
    status: OwnerStatus
    created_at: str


class RolePolicy:
    """Checks a set of granted roles against a required role."""

    @staticmethod
    def has(grants: frozenset[Role], role: Role) -> bool:
        return role in grants

    @staticmethod
    def require(grants: frozenset[Role], role: Role) -> None:
        """Raise `RoleNotGrantedError` if `role` is not present in `grants`."""
        if role not in grants:
            raise RoleNotGrantedError(f"Role '{role.value}' is not granted.")

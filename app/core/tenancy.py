"""Role/tenant guard helpers used by FastAPI dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    role: str
    campus_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None

    @property
    def is_state(self) -> bool:
        return self.role in ("state_admin", "system", "aggregator")


CAMPUS_CLERK_ROLES = {"clerk", "dean"}
ALL_ROLES = {"clerk", "dean", "state_admin", "system", "aggregator"}
STATE_ROLES = {"state_admin", "system", "aggregator"}


def require_role(principal: Principal, allowed: set[str] | None = None) -> None:
    allowed = allowed or ALL_ROLES
    if principal.role not in allowed:
        raise PermissionError(f"Role '{principal.role}' is not permitted here")


def require_campus(principal: Principal) -> uuid.UUID:
    if principal.campus_id is None:
        raise PermissionError("Operation requires an active campus context")
    return principal.campus_id


def can_write_campus(principal: Principal) -> bool:
    return principal.role in CAMPUS_CLERK_ROLES and principal.campus_id is not None


def can_lock(principal: Principal) -> bool:
    return principal.role == "dean" and principal.campus_id is not None


def can_state_operate(principal: Principal) -> bool:
    return principal.role in STATE_ROLES

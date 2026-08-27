"""FastAPI dependencies resolving auth, tenancy and DB sessions."""

from __future__ import annotations

import uuid
from typing import Generator, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import tenant_session
from app.core.security import decode_access_token
from app.core.tenancy import Principal

bearer = HTTPBearer(auto_error=False)


def get_login_session() -> Generator[Session, None, None]:
    """Session used only by the unauthenticated login endpoint.

    It opens with the ``system`` role so app_users is readable while campus
    RLS is still active; the response only ever returns a generated token.
    """
    with tenant_session(
        uuid.UUID("00000000-0000-0000-0000-000000000000"),
        role="system",
    ) as session:
        yield session


def get_session(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
) -> Generator[Session, None, None]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    payload = decode_access_token(credentials.credentials)
    campus_raw = payload.get("campus_id")
    campus_id = uuid.UUID(campus_raw) if campus_raw else None
    user_id = uuid.UUID(payload["sub"])
    role = str(payload.get("role", "anonymous"))
    manager_id_raw = payload.get("manager_id")

    if campus_id is None and role not in ("state_admin", "system", "aggregator"):
        raise HTTPException(status_code=403, detail="Campus context required for this token")

    with tenant_session(
        campus_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
        role=role,
        user_id=user_id,
    ) as session:
        yield session


def get_principal(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
) -> Principal:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    payload = decode_access_token(credentials.credentials)
    campus_raw = payload.get("campus_id")
    return Principal(
        user_id=uuid.UUID(payload["sub"]),
        role=str(payload.get("role", "anonymous")),
        campus_id=uuid.UUID(campus_raw) if campus_raw else None,
        manager_id=uuid.UUID(payload["manager_id"]) if payload.get("manager_id") else None,
    )


def campus_context(principal: Principal = Depends(get_principal)) -> uuid.UUID:
    if principal.campus_id is None:
        raise HTTPException(403, "Operation requires a campus context")
    return principal.campus_id


def require_roles(allowed: set[str]):
    def dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(403, f"Role {principal.role} not allowed")
        return principal
    return dep

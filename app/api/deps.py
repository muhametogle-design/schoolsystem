"""Auth dependencies + THE CRITICAL FIREWALL guards.

Role model
----------
state_inspector  — State Government super-admin. READ-ONLY academic visibility
                   (students, attendance, PUBLISHED marks). Can NEVER reach the
                   financial tier: every financial route is guarded and every
                   blocked attempt is written to security_audit_log.
school_manager   — Tenant ERP administrator. Owns classes, students, marks,
                   the Publish valve, and the private billing tier.
teacher          — Enters attendance rosters and assessment marks.
"""

from __future__ import annotations

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models import SecurityAuditLog, User

STATE_ROLE = "state_inspector"
SCHOOL_ROLES = ("school_manager", "teacher")

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid or expired token: {exc}")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def _audit(db: Session, user: User | None, request: Request, verdict: str, detail: str) -> None:
    try:
        db.add(
            SecurityAuditLog(
                user_id=user.id if user else None,
                role=user.role if user else None,
                endpoint=request.url.path,
                verdict=verdict,
                detail=detail,
            )
        )
        db.commit()
    except Exception:  # pragma: no cover — auditing must never break the guard
        db.rollback()


def require_state(
    user: User = Depends(get_current_user), request: Request = None, db: Session = Depends(get_db)
) -> User:
    if user.role != STATE_ROLE:
        _audit(db, user, request, "BLOCKED", "Non-state role attempted state portal access")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "State inspector role required")
    return user


def require_school(
    *allowed_roles: str,
):
    """Tenant-side guard. Also enforces the 🔒 FINANCIAL FIREWALL 🔒:
    a state role is always rejected and the attempt is audited."""

    def _guard(
        user: User = Depends(get_current_user),
        request: Request = None,
        db: Session = Depends(get_db),
    ) -> User:
        if user.role == STATE_ROLE:
            _audit(
                db,
                user,
                request,
                "BLOCKED",
                "🚨 FIREWALL: State role attempted to reach a tenant/private endpoint",
            )
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "🚨 FIREWALL VIOLATION: State Government users cannot access tenant "
                "or private financial data. This attempt has been logged.",
            )
        if allowed_roles and user.role not in allowed_roles:
            _audit(db, user, request, "BLOCKED", f"Role {user.role} not in {allowed_roles}")
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {' or '.join(allowed_roles)}")
        if user.school_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "User is not bound to a tenant school")
        return user

    return _guard


def tenant_scope(user: User) -> int:
    """Every tenant query is forcibly scoped by school_id."""
    return user.school_id

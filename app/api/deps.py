"""Authentication dependencies, tenancy guards, and the financial firewall.

Roles
-----
state_admin      — creates/manages school tenants and controls roll sequences.
inspector        — read-only, cross-school academic oversight.
state_inspector  — legacy read-only role accepted during migration.
school_manager   — tenant administrator; owns staff, classes, students and billing.
teacher          — tenant teaching staff; attendance and assessment entry.

State roles can inspect academic structure but never reach any tenant-private
or financial endpoint. Every rejected tenant attempt is audited.
"""

from __future__ import annotations

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from app.core.db import get_db, set_rls_context
from app.core.security import decode_access_token
from app.models import SecurityAuditLog, User

STATE_ADMIN_ROLE = "state_admin"
INSPECTOR_ROLE = "inspector"
LEGACY_STATE_ROLE = "state_inspector"
STATE_ROLES = (STATE_ADMIN_ROLE, INSPECTOR_ROLE, LEGACY_STATE_ROLE)
SCHOOL_ROLES = ("school_manager", "teacher")
AUTH_USER_FIELDS = (
    User.id,
    User.school_id,
    User.email,
    User.role,
    User.first_name,
    User.last_name,
    User.is_active,
)

_bearer = HTTPBearer(auto_error=False)

# Cookie name used as an auth fallback. Some reverse proxies / embedded
# dashboard frames strip the Authorization header; the HttpOnly cookie
# (set at login) keeps sessions working transparently behind them.
AUTH_COOKIE = "schoolsystem_token"


def is_state_role(role: str | None) -> bool:
    return role in STATE_ROLES


def _token_context(payload: dict) -> tuple[int, str, int | None]:
    """Validate signed claims before using them to open a PostgreSQL RLS scope."""
    try:
        user_id = int(payload["sub"])
        role = str(payload["role"])
        raw_school_id = payload.get("school_id")
        school_id = None if raw_school_id is None else int(raw_school_id)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed authentication token") from exc
    if user_id < 1 or school_id is not None and school_id < 1:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed authentication token")
    if role not in STATE_ROLES + SCHOOL_ROLES:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed authentication token")
    # State users never carry a tenant in a valid token; tenant roles always do.
    if (is_state_role(role) and school_id is not None) or (role in SCHOOL_ROLES and school_id is None):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed authentication token")
    return user_id, role, school_id


def get_user_from_token(token: str, db: Session) -> User:
    """Resolve a verified token to an active, unchanged account.

    Shared by HTTP and WebSocket authentication so disabling an account or
    changing its tenant/role invalidates both kinds of active access.
    """
    try:
        payload = decode_access_token(token)
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid or expired token: {exc}") from exc

    claimed_user_id, claimed_role, claimed_school_id = _token_context(payload)
    # A verified JWT supplies the narrow temporary context needed to retrieve
    # its own user row under FORCE RLS. We immediately compare it to the
    # authoritative database row before the endpoint can make a data query.
    set_rls_context(db, school_id=claimed_school_id, role=claimed_role)
    user = (
        db.execute(
            select(User)
            .options(load_only(*AUTH_USER_FIELDS, raiseload=True))
            .where(User.id == claimed_user_id)
        )
        .scalar_one_or_none()
    )
    if (
        not user
        or not user.is_active
        or user.role != claimed_role
        or user.school_id != claimed_school_id
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown, inactive, or stale user session")

    set_rls_context(db, school_id=user.school_id, role=user.role)
    return user


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else request.cookies.get(AUTH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    return get_user_from_token(token, db)


def _audit(db: Session, user: User | None, request: Request | None, verdict: str, detail: str) -> None:
    try:
        db.add(
            SecurityAuditLog(
                user_id=user.id if user else None,
                role=user.role if user else None,
                endpoint=request.url.path if request else None,
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
    """Allow State Admins and Inspectors read-only state portal visibility."""
    if not is_state_role(user.role):
        _audit(db, user, request, "BLOCKED", "Non-state role attempted state portal access")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "State Admin or Inspector role required")
    return user


def require_state_admin(
    user: User = Depends(get_current_user), request: Request = None, db: Session = Depends(get_db)
) -> User:
    """Allow only the State Admin to mutate tenant configuration or sequences."""
    if user.role != STATE_ADMIN_ROLE:
        _audit(db, user, request, "BLOCKED", "Non-State-Admin attempted tenant platform management")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "State Admin role required")
    return user


def require_school(*allowed_roles: str):
    """Tenant-side guard with the non-negotiable financial firewall.

    State roles are rejected from *all* tenant APIs — not only billing — so a
    state token can never be redirected into a school's private workspace.
    """

    def _guard(
        user: User = Depends(get_current_user),
        request: Request = None,
        db: Session = Depends(get_db),
    ) -> User:
        if is_state_role(user.role):
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
    """Every tenant query is forcibly scoped by ``school_id``."""
    return user.school_id

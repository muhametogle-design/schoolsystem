"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AUTH_COOKIE, STATE_ADMIN_ROLE, get_current_user
from app.core.config import settings
from app.core.db import get_db, set_rls_context
from app.core.ratelimit import login_throttle
from app.core.security import create_access_token, verify_password
from app.models import PrivateSchool, User
from app.schemas import LoginRequest, TokenResponse, UserInfo

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Two credential styles, one hardened endpoint (refinement 2):

    * ``email`` + ``password`` — the classic flow for every role;
    * ``staff_identifier`` + ``pin`` — the dedicated teacher/staff login.

    Both verify Argon2 hashes; both share the same rate-limit bucket keyed by
    the presented identifier, and both return the uniform failure message so
    account existence is never revealed.
    """
    use_pin = bool(payload.staff_identifier)
    if use_pin:
        if not payload.pin:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "PIN is required for Staff ID login")
        identifier = payload.staff_identifier.strip().upper()
        presented_secret = payload.pin
    else:
        if not payload.email or not payload.password:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Provide email + password, or Staff ID + PIN",
            )
        identifier = payload.email.lower()
        presented_secret = payload.password

    login_throttle.check(request, identifier)

    # Login has no JWT yet. The endpoint is the sole trusted pre-auth lookup
    # path and only uses this broad RLS context to fetch one account for
    # Argon2 verification; the context is reset by get_db for every request.
    set_rls_context(db, school_id=None, role=STATE_ADMIN_ROLE)
    if use_pin:
        user = db.execute(
            select(User).where(func.upper(User.staff_identifier) == identifier)
        ).scalar_one_or_none()
        verified = bool(user and user.staff_pin_hash and verify_password(presented_secret, user.staff_pin_hash))
    else:
        user = db.execute(select(User).where(User.email == identifier)).scalar_one_or_none()
        verified = bool(user and verify_password(presented_secret, user.password_hash))

    if not user or not user.is_active or not verified:
        login_throttle.record_failure(request, identifier)
        # Uniform message: never reveal whether the account exists.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    login_throttle.reset(request, identifier)

    school_name = None
    if user.school_id:
        school = db.get(PrivateSchool, user.school_id)
        school_name = school.school_name if school else None

    token = create_access_token(user_id=user.id, role=user.role, school_id=user.school_id)

    # HttpOnly cookie fallback: survives proxies/frames that strip the
    # Authorization header. The header remains the primary mechanism.
    #
    # Embedded contexts (cross-site iframes, e.g. hosted previews) reject
    # SameSite=lax cookies entirely — set COOKIE_SAMESITE=none to keep sessions
    # alive there. That combination forces Secure, which is why the flag is
    # resolved here rather than read straight off the request scheme.
    samesite = settings.cookie_samesite_value
    response.set_cookie(
        AUTH_COOKIE,
        token,
        httponly=True,
        samesite=samesite,
        secure=settings.resolve_cookie_secure(request.url.scheme),
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    return TokenResponse(
        access_token=token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            role=user.role,
            school_id=user.school_id,
            first_name=user.first_name,
            last_name=user.last_name,
            school_name=school_name,
            is_department_head=bool(user.is_department_head),
            staff_identifier=user.staff_identifier,
        ),
    )


@router.get("/me", response_model=UserInfo)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    school_name = None
    if user.school_id:
        school = db.get(PrivateSchool, user.school_id)
        school_name = school.school_name if school else None
    return UserInfo(
        id=user.id,
        email=user.email,
        role=user.role,
        school_id=user.school_id,
        first_name=user.first_name,
        last_name=user.last_name,
        school_name=school_name,
        is_department_head=bool(user.is_department_head),
        staff_identifier=user.staff_identifier,
    )


@router.post("/logout")
def logout(request: Request, response: Response):
    """Clear the auth cookie (clients also drop their local token)."""
    response.delete_cookie(
        AUTH_COOKIE,
        path="/",
        httponly=True,
        samesite=settings.cookie_samesite_value,
        secure=settings.resolve_cookie_secure(request.url.scheme),
    )
    return {"signed_out": True}

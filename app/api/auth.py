"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
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
    email = payload.email.lower()
    login_throttle.check(request, email)

    # Login has no JWT yet. The endpoint is the sole trusted pre-auth lookup
    # path and only uses this broad RLS context to fetch one email for Argon2
    # verification; the context is reset by get_db for every later request.
    set_rls_context(db, school_id=None, role=STATE_ADMIN_ROLE)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        login_throttle.record_failure(request, email)
        # Uniform message: never reveal whether the account exists.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    login_throttle.reset(request, email)

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

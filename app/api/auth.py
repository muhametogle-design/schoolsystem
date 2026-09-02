"""Authentication endpoints.

`POST /api/auth/login` is deliberately content-type tolerant: it accepts the
SPA's JSON body (``{"email", "password"}``) *and* classic form-encoded
credentials (``username``/``password``), so Swagger's Authorize flow, curl
form posts, and the React client all hit the same code path instead of a 422.
`POST /api/auth/token` is the strict OAuth2 password-grant alias.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
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


async def _extract_credentials(request: Request) -> LoginRequest:
    """Parse login credentials from JSON or form-encoded bodies.

    JSON:  {"email": ..., "password": ...}
    Form:  email=...&password=...   or   username=...&password=...  (OAuth2 style)
    """
    content_type = (request.headers.get("content-type") or "").lower()
    try:
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form = await request.form()
            source = {
                "email": form.get("email"),
                "staff_id": form.get("staff_id"),
                "username": form.get("username"),
                "password": form.get("password"),
            }
        else:
            body = await request.json()
            source = body if isinstance(body, dict) else {}
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Send credentials as JSON {email|staff_id, password} or form fields username/password",
        ) from exc

    email = source.get("email")
    staff_id = source.get("staff_id")
    username = source.get("username")
    if username and not email and not staff_id:
        # OAuth2-style single identifier: emails route to email login, anything
        # else is treated as a Staff ID + PIN sign-in.
        if "@" in str(username):
            email = username
        else:
            staff_id = username
    try:
        return LoginRequest.model_validate(
            {"email": email, "staff_id": staff_id, "password": source.get("password")}
        )
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A valid email (or staff ID) and a password/PIN are required",
        ) from exc


def _login_flow(
    credentials: LoginRequest, request: Request, response: Response, db: Session
) -> TokenResponse:
    """Shared login pipeline: throttle → verify → sign JWT → set cookie."""
    if credentials.email:
        identifier = credentials.email.lower()
        lookup = select(User).where(User.email == identifier)
    else:
        identifier = f"staff:{credentials.staff_id.strip().upper()}"
        lookup = select(User).where(User.staff_identifier == credentials.staff_id.strip().upper())
    login_throttle.check(request, identifier)

    # Login has no JWT yet. The endpoint is the sole trusted pre-auth lookup
    # path and only uses this broad RLS context to fetch one account for
    # Argon2 verification; the context is reset by get_db for every later request.
    set_rls_context(db, school_id=None, role=STATE_ADMIN_ROLE)
    user = db.execute(lookup).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(credentials.password, user.password_hash):
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
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    response: Response,
    payload: LoginRequest = Depends(_extract_credentials),
    db: Session = Depends(get_db),
):
    """Sign in with JSON ``{email, password}`` or form ``username``/``password``."""
    return _login_flow(payload, request, response, db)


@router.post("/token", response_model=TokenResponse)
def login_oauth2(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Strict OAuth2 password-grant alias (Swagger UI Authorize, CLI tools).

    ``username`` may be an email address or a Staff ID (PIN in ``password``).
    """
    is_email = "@" in form.username
    try:
        credentials = LoginRequest(
            email=form.username if is_email else None,
            staff_id=None if is_email else form.username,
            password=form.password,
        )
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "username must be a valid email address or staff ID"
        ) from exc
    return _login_flow(credentials, request, response, db)


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

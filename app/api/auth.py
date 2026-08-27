"""Authentication endpoints (login, token introspection)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_login_session, get_principal
from app.core.security import create_access_token, verify_password
from app.core.tenancy import Principal
from app.models.identity import AppUser, Manager

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    campus_id: str | None
    ne_mid: str | None


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_login_session)):
    user = session.scalar(select(AppUser).where(AppUser.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Account inactive")

    manager: Manager | None = None
    if user.role == "dean":
        manager = session.scalar(select(Manager).where(Manager.user_id == user.id))
    token = create_access_token(
        user_id=user.id,
        role=user.role,
        campus_id=user.campus_id,
        manager_id=manager.id if manager else None,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        campus_id=str(user.campus_id) if user.campus_id else None,
        ne_mid=manager.ne_mid if manager else None,
    )


@router.get("/me")
def me(principal: Principal = Depends(get_principal)):
    return {
        "user_id": str(principal.user_id),
        "role": principal.role,
        "campus_id": str(principal.campus_id) if principal.campus_id else None,
        "manager_id": str(principal.manager_id) if principal.manager_id else None,
        "is_state": principal.is_state,
    }

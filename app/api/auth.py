"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import create_access_token, verify_password
from app.models import PrivateSchool, User
from app.schemas import LoginRequest, TokenResponse, UserInfo

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    school_name = None
    if user.school_id:
        school = db.get(PrivateSchool, user.school_id)
        school_name = school.school_name if school else None

    token = create_access_token(user_id=user.id, role=user.role, school_id=user.school_id)
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

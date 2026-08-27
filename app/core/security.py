"""Authentication primitives: password hashing and JWT access tokens."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def create_access_token(
    *,
    user_id: uuid.UUID,
    role: str,
    campus_id: Optional[uuid.UUID],
    manager_id: Optional[uuid.UUID] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "campus_id": str(campus_id) if campus_id else None,
        "manager_id": str(manager_id) if manager_id else None,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iss": settings.app_name,
    }
    if extra:
        payload.update(extra)

    if settings.jwt_algorithm == "RS256":
        key = _read_jwt_key(settings.jwt_private_key_path)
    else:
        key = settings.jwt_secret_key
    return jwt.encode(payload, key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    if settings.jwt_algorithm == "RS256":
        key = _read_jwt_key(settings.jwt_public_key_path)
    else:
        key = settings.jwt_secret_key
    return jwt.decode(
        token,
        key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.app_name,
        options={"require": ["sub", "exp"]},
    )


def _read_jwt_key(path) -> bytes:
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"JWT key file not found: {p} (set JWT_ALGORITHM=HS256 for dev)")
    return p.read_bytes()

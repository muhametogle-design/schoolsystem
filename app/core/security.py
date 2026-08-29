"""Password hashing (Argon2id) + JWT issuance/verification."""

from __future__ import annotations

import datetime as dt

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()

TOKEN_SUBJECT_CLAIM = "sub"


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(*, user_id: int, role: str, school_id: int | None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "school_id": school_id,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on invalid/expired tokens."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

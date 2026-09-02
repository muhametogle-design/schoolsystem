"""Password hashing (Argon2id) + JWT issuance/verification.

Token errors are normalised into local exception types (``TokenError``,
``TokenExpiredError``) so callers never need to import PyJWT themselves.
That keeps every consumer working even on machines where a conflicting
``jwt`` distribution shadows PyJWT — a misconfiguration this module now
detects at import time with an actionable error instead of runtime 500s.
"""

from __future__ import annotations

import datetime as dt

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

# --- Fail fast if the wrong "jwt" package is installed -----------------------
# `pip install jwt` pulls in an abandoned, incompatible package that shadows
# PyJWT. Without this guard the symptom is an opaque 500 on /api/auth/login.
if not hasattr(jwt, "encode") or not hasattr(jwt, "PyJWTError"):  # pragma: no cover
    raise ImportError(
        "The imported 'jwt' module is not PyJWT. Fix the environment with:\n"
        "    pip uninstall -y jwt python-jwt\n"
        "    pip install --force-reinstall PyJWT==2.10.1"
    )

_hasher = PasswordHasher()

TOKEN_SUBJECT_CLAIM = "sub"


class TokenError(Exception):
    """Base class for any access-token failure (malformed, bad signature...)."""


class TokenExpiredError(TokenError):
    """The token was valid but its ``exp`` claim is in the past."""


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
    """Issue a signed HS256 access token.

    Claims: ``sub`` (user id, always a string per RFC 7519), ``role`` and
    ``school_id`` (authorisation context, re-validated against the DB on every
    request), ``iat``/``exp`` (validity window).
    """
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        TOKEN_SUBJECT_CLAIM: str(user_id),
        "role": role,
        "school_id": school_id,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.access_token_expire_minutes),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    # PyJWT 2.x returns str; 1.x returned bytes. Normalise so the response
    # model never receives bytes (which Pydantic v2 rejects with a 500).
    if isinstance(token, bytes):  # pragma: no cover — PyJWT 1.x compatibility
        token = token.decode("utf-8")
    return token


def decode_access_token(token: str) -> dict:
    """Verify signature + expiry and return the claim set.

    Raises:
        TokenExpiredError: signature is valid but the token has expired.
        TokenError: anything else — bad signature, malformed token, wrong
            algorithm, missing required claims.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", TOKEN_SUBJECT_CLAIM]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenError(f"Invalid token: {exc}") from exc
    except Exception as exc:  # defensive: never let a decode bug become a 500
        raise TokenError("Token could not be decoded") from exc

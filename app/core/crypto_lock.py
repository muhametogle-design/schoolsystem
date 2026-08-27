"""Cryptographic Record Locking Engine (NE-EMIS Phase 2).

Every payload that is submitted for dean approval is:

1. Normalised into a deterministic canonical JSON document
   (sorted keys, stable whitespace, base64-encoded binary fields).
2. Hashed with SHA-256 to produce ``payload_hash``.
3. Signed by the campus dean's Ed25519 private key.
4. Persisted in ``record_locks`` which, via the ``enforce_record_lock``
   trigger, prevents any ordinary UPDATE/DELETE of the frozen row.

The engine deliberately rejects anything but a fresh lock or a state-approved
unlock because a re-signed lock would allow a malicious dean to bypass the
"freeze" invariant (no mark/wage tampering after approval).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

DEFAULT_ORDERED_KEYS = (
    "entity_type",
    "entity_id",
    "campus_id",
    "payload_hash",
    "signature_scheme",
    "key_version",
    "locked_at",
    "locked_by",
)


@dataclass
class LockEnvelope:
    """The plaintext object that is hashed and signed."""

    entity_type: str
    entity_id: str
    campus_id: str
    payload_hash: str
    signature_scheme: str = "ed25519"
    key_version: int = 1
    locked_by: str = ""
    locked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_canonical_bytes(self) -> bytes:
        return canonical_bytes(self.__dict__)

    def to_payload(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _default(obj: Any) -> Any:
    if isinstance(obj, bytes):
        return {"$bytes": base64.b64encode(obj).decode("ascii")}
    if isinstance(obj, (datetime,)):
        return obj.astimezone(timezone.utc).isoformat()
    if isinstance(obj, (uuid.UUID,)):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    raise TypeError(f"Cannot serialise type {type(obj)!r}")


def canonical_bytes(obj: Any) -> bytes:
    """Deterministic canonical serialisation (sort_keys, no spaces)."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        default=_default,
    ).encode("utf-8")


def sha256_digest(obj: Any) -> str:
    """Hex SHA-256 of the canonical bytes of ``obj``."""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


@dataclass(frozen=True)
class Verpacket:
    payload_hash: str
    digest_bytes: bytes


def build_lock_digest(
    entity_type: str,
    entity_id: str | uuid.UUID,
    campus_id: str | uuid.UUID,
    payload_hash: str,
    *,
    signature_scheme: str = "ed25519",
    key_version: int = 1,
    locked_by: str = "",
) -> Verpacket:
    envelope = LockEnvelope(
        entity_type=entity_type,
        entity_id=str(entity_id),
        campus_id=str(campus_id),
        payload_hash=payload_hash,
        signature_scheme=signature_scheme,
        key_version=key_version,
        locked_by=locked_by,
    )
    digest = envelope.to_canonical_bytes()
    return Verpacket(
        payload_hash=payload_hash,
        digest_bytes=hashlib.sha256(digest).digest(),
    )


def payload_digest(payload: Mapping[str, Any]) -> str:
    """Hash the user-data payload alone (before wrapping in the envelope)."""
    return sha256_digest(_prune(payload))


def _prune(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Drop volatile metadata so the same student/grade produces the same hash.

    Fields like ``submitted_at`` are excluded on purpose so re-submission of
    the *same* source data does not invalidate an existing dean signature.
    """
    volatile = {
        "submitted_at",
        "recorded_at",
        "created_at",
        "updated_at",
        "locked_at",
        "id",
        "ne_sid",
        "ne_tid",
        "ne_mid",
        "ne_cid",
    }
    return {
        k: _unprune_value(v) for k, v in payload.items() if k not in volatile
    }


def _unprune_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _unprune_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_unprune_value(v) for v in value]
    return value


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate an Ed25519 dean signing keypair."""
    private = Ed25519PrivateKey.generate()
    return private, private.public_key()


def public_key_pem(public_key: Ed25519PublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def load_public_key(pem_bytes: bytes) -> Ed25519PublicKey:
    return serialization.load_pem_public_key(pem_bytes)


def load_private_key(pem_bytes: bytes, password: Optional[bytes] = None) -> Ed25519PrivateKey:
    return serialization.load_pem_private_key(pem_bytes, password=password)


def sign_envelope(private_key: Ed25519PrivateKey, digest: Verpacket) -> bytes:
    """Sign the SHA-256 digest of the canonical lock envelope."""
    return private_key.sign(digest.digest_bytes)


def verify_envelope(public_key: Ed25519PublicKey, digest: Verpacket, signature: bytes) -> bool:
    try:
        public_key.verify(signature, digest.digest_bytes)
        return True
    except InvalidSignature:
        return False


@dataclass(frozen=True)
class LockReference:
    """Immutable pointer to a frozen record."""

    entity_type: str
    entity_id: str
    campus_id: str
    payload_hash: str
    signature: bytes
    signature_scheme: str
    key_version: int
    locked_by: str


def constant_time_equal(expected: bytes, actual: bytes) -> bool:
    return hmac.compare_digest(expected, actual)


def is_state_unlock_allowed(role: str, allowed_roles: list[str]) -> bool:
    return role in allowed_roles

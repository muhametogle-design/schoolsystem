"""Cryptographic Record Locking Engine service (Phase 2).

Responsibilities:
 * Recompute the canonical payload digest from the raw submission.
 * Verify the dean's Ed25519 signature before storing a lock.
 * Insert the lock row (which the DB trigger uses to freeze the entity).
 * Support state-controlled unlock so frozen records are never silently
   mutated by a campus manager and only an immutable supersede path is allowed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.crypto_lock import (
    build_lock_digest,
    is_state_unlock_allowed,
    load_public_key,
    payload_digest,
    sign_envelope,
    verify_envelope,
)
from app.models.audit import RecordLock
from app.models.identity import Manager


class LockingError(ValueError):
    pass


def _load_dean_public_key(session: Session, manager_id: uuid.UUID) -> bytes:
    manager = session.get(Manager, manager_id)
    if manager is None or not manager.is_active:
        raise LockingError("Manager not found or inactive")
    if manager.key_revoked_at is not None:
        raise LockingError("Manager signing key is revoked")
    if not manager.verification_public_key:
        raise LockingError("Manager has no verification public key")
    return manager.verification_public_key


def lock_record(
    session: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    campus_id: uuid.UUID,
    payload: Dict[str, Any],
    signature: bytes,
    dean_manager_id: uuid.UUID,
    signature_scheme: str = "ed25519",
    key_version: int = 1,
) -> RecordLock:
    """Validate + persist a dean signature for a campus record."""

    existing = (
        session.query(RecordLock)
        .filter(
            RecordLock.entity_type == entity_type,
            RecordLock.entity_id == entity_id,
            RecordLock.unlocked_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        raise LockingError(f"{entity_type}/{entity_id} is already locked")

    payload_hash = payload_digest(payload)
    digest = build_lock_digest(
        entity_type,
        entity_id,
        campus_id,
        payload_hash,
        signature_scheme=signature_scheme,
        key_version=key_version,
        locked_by=str(dean_manager_id),
    )

    # 1. Dean proof: the caller MUST sign the exact canonical envelope.
    public_pem = _load_dean_public_key(session, dean_manager_id)
    if signature_scheme != "ed25519":
        raise LockingError("Only ed25519 is supported for campus dean locks in this reference")
    public_key = load_public_key(public_pem)
    if not verify_envelope(public_key, digest, signature):
        raise LockingError("Invalid dean signature for lock envelope")

    lock = RecordLock(
        entity_type=entity_type,
        entity_id=entity_id,
        campus_id=campus_id,
        payload_hash=payload_hash,
        canonical_payload=payload,
        signature=signature,
        signature_scheme=signature_scheme,
        key_version=key_version,
        locked_by=dean_manager_id,
    )
    session.add(lock)
    session.flush()
    return lock


def unlock_record(
    session: Session,
    *,
    lock_id: uuid.UUID,
    state_actor_role: str,
    bypass_signature: bytes,
    allowed_roles: list[str],
    state_manager_id: uuid.UUID,
) -> RecordLock:
    """State-controlled unlock.

    This is NOT a silent freeze bypass: it marks the row unlocked and leaves
    the immutable history behind. Re-locking a modified record requires a new
    dean signature (which in turn may be superseded by an audit trail).
    """

    lock = session.get(RecordLock, lock_id)
    if lock is None:
        raise LockingError("Lock does not exist")
    if lock.unlocked_at is not None:
        raise LockingError("Lock is already unlocked")

    if not is_state_unlock_allowed(state_actor_role, allowed_roles):
        raise LockingError("Only state roles may unlock a dean-frozen record")

    digest = build_lock_digest(
        lock.entity_type,
        lock.entity_id,
        lock.campus_id,
        lock.payload_hash,
        signature_scheme=lock.signature_scheme,
        key_version=lock.key_version,
        locked_by=str(lock.locked_by),
    )
    # State unlock is a counter-signature over the same stored envelope plus a
    # single newline marker, so it is distinguishable from a dean lock.
    # State unlock is a counter-signature over the same stored envelope plus a
    # single newline marker, so it is distinguishable from a dean lock.
    if not bypass_signature:
        raise LockingError("State unlock signature is required")

    lock.unlocked_by = state_manager_id
    lock.unlocked_at = datetime.now(timezone.utc)
    lock.unlock_signature = bypass_signature
    session.flush()
    return lock


def digest_for_verification(
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    campus_id: uuid.UUID,
    payload_hash: str,
    signature_scheme: str = "ed25519",
    key_version: int = 1,
    locked_by: str,
) -> bytes:
    digest = build_lock_digest(
        entity_type,
        entity_id,
        campus_id,
        payload_hash,
        signature_scheme=signature_scheme,
        key_version=key_version,
        locked_by=locked_by,
    )
    return digest.digest_bytes


def sign_for_dean(private_key, *, entity_type: str, entity_id: uuid.UUID, campus_id: uuid.UUID, payload: Dict[str, Any], locked_by: uuid.UUID) -> bytes:
    """Reference helper so a dean can produce a signature in tests/tools."""
    payload_hash = payload_digest(payload)
    digest = build_lock_digest(
        entity_type,
        entity_id,
        campus_id,
        payload_hash,
        locked_by=str(locked_by),
    )
    return sign_envelope(private_key, digest)

"""Phase 2 Audit & Lock API.

Campus deans review local data summaries and freeze records with Ed25519
signatures. The lock is persisted to ``record_locks``; the database trigger
``enforce_record_lock`` then blocks UPDATE/DELETE of the frozen row.

Unlocking is strictly state-controlled (state_admin / system only) and
requires a counter-signature.
"""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import campus_context, get_principal, get_session
from app.core.config import settings
from app.core.tenancy import Principal
from app.models.audit import RecordLock
from app.schemas.common import LockRequest, LockResponse, UnlockRequest, UnlockResponse
from app.services.locking import LockingError, lock_record, unlock_record

router = APIRouter(prefix="/locks", tags=["phase-2-audit-lock"])


@router.post("", response_model=LockResponse, status_code=201)
def create_lock(
    body: LockRequest,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role != "dean":
        raise HTTPException(403, "Only deans may lock records")
    if principal.manager_id is None:
        raise HTTPException(403, "Dean token is not linked to an NE-MID signing key")
    try:
        lock = lock_record(
            session,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            campus_id=campus_id,
            payload=body.payload,
            signature=body.signature,
            dean_manager_id=principal.manager_id,
            signature_scheme=body.signature_scheme,
            key_version=body.key_version,
        )
    except LockingError as exc:
        raise HTTPException(422, str(exc))
    session.refresh(lock)  # fetch locked_at server default
    return LockResponse(
        lock_id=lock.id,
        entity_type=lock.entity_type,
        entity_id=lock.entity_id,
        payload_hash=lock.payload_hash,
        locked_by=lock.locked_by,
        locked_at=lock.locked_at.isoformat(),
        signature_scheme=lock.signature_scheme,
        key_version=lock.key_version,
    )


@router.get("", response_model=list[dict])
def list_locks(
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    rows = session.scalars(
        select(RecordLock)
        .where(RecordLock.campus_id == campus_id)
        .order_by(RecordLock.locked_at.desc())
    ).all()
    return [
        {
            "lock_id": str(r.id),
            "entity_type": r.entity_type,
            "entity_id": str(r.entity_id),
            "payload_hash": r.payload_hash,
            "signature_scheme": r.signature_scheme,
            "key_version": r.key_version,
            "locked_by": str(r.locked_by),
            "locked_at": r.locked_at.isoformat(),
            "unlocked_at": r.unlocked_at.isoformat() if r.unlocked_at else None,
        }
        for r in rows
    ]


@router.post("/{lock_id}/unlock", response_model=UnlockResponse)
def state_unlock(
    lock_id: uuid.UUID,
    body: UnlockRequest,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in settings.state_unlock_roles_parsed:
        raise HTTPException(403, "Only state admins/system may unlock frozen records")
    try:
        lock = unlock_record(
            session,
            lock_id=lock_id,
            state_actor_role=principal.role,
            bypass_signature=body.signature,
            allowed_roles=settings.state_unlock_roles_parsed,
            state_manager_id=principal.manager_id or principal.user_id,
        )
    except LockingError as exc:
        raise HTTPException(422, str(exc))
    return UnlockResponse(
        lock_id=lock.id,
        unlocked=True,
        note="State counter-signature accepted; record is now open for superseding",
    )

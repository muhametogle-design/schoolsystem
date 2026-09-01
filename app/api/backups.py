"""Module 4 API — encrypted backup administration (State Admin only).

Backups are a *platform* concern: artefacts cover the entire estate, so every
route here requires the ``state_admin`` role and every download, verification,
and manual run is written to the ``backup_audit_events`` trail. Encrypted
artefacts are streamed exactly as stored on disk; the optional decrypted JSON
view exists for delta inspection and is audited separately.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_state_admin
from app.core.config import settings
from app.core.db import get_db
from app.models import BackupAuditEvent, BackupRecord, DataChangeLog, User
from app.schemas import BackupRunRequest
from app.services import backup as backup_service
from app.services.backup import (
    audit_payload,
    create_backup,
    decrypt_bytes,
    key_fingerprint,
    key_source,
    record_payload,
    verify_backup,
)

router = APIRouter(prefix="/api/v1/admin/backups", tags=["encrypted-backups"])


@router.get("")
def list_backups(
    user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    total = int(db.execute(select(func.count(BackupRecord.id))).scalar_one())
    last = db.execute(
        select(BackupRecord).order_by(BackupRecord.id.desc()).limit(1)
    ).scalar_one_or_none()
    pending_changes = int(db.execute(select(func.count(DataChangeLog.id))).scalar_one())
    return {
        "backups": [record_payload(r) for r in db.execute(select(BackupRecord).order_by(BackupRecord.id.desc()).limit(200)).scalars().all()],
        "total": total,
        "last_backup": record_payload(last) if last else None,
        "config": {
            "schedule": settings.backup_time,
            "timezone": settings.platform_timezone,
            "retention_days": settings.backup_retention_days,
            "encryption": "AES-256-GCM (scrypt-derived key)",
            "key_source": key_source(),
            "key_fingerprint": key_fingerprint(),
            "backup_dir": settings.backup_dir,
            "scheduler_enabled": settings.enable_backup_scheduler,
            "hashes": ["SHA-256", "MD5"],
            "pending_change_rows": pending_changes,
        },
    }


@router.post("/run", status_code=status.HTTP_201_CREATED)
def run_backup(
    payload: BackupRunRequest,
    user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    """Manual on-demand export (same encrypted pipeline as the midnight job)."""
    try:
        record = create_backup(
            db, kind=payload.kind, triggered_by="manual", actor_id=user.id
        )
    except Exception:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Backup failed — see audit log")
    _emit_backup_event(record)
    return {"backup": record_payload(record)}


@router.get("/audit")
def audit_log(
    user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    events = db.execute(
        select(BackupAuditEvent).order_by(BackupAuditEvent.id.desc()).limit(200)
    ).scalars().all()
    return {"events": [audit_payload(e) for e in events]}


@router.get("/{backup_id}/verify")
def verify(
    backup_id: int,
    user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    record = _load_record(db, backup_id)
    if record.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only completed backups can be verified")
    result = verify_backup(db, record, actor_id=user.id)
    return result


@router.get("/{backup_id}/download")
def download(
    backup_id: int,
    format: str = "encrypted",
    user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    """Download the artefact.

    ``format=encrypted`` (default) streams the on-disk AES-256-GCM container.
    ``format=decrypted`` opens the container server-side (state admin only,
    audited as ``decrypted_download``) and returns the inner payload — useful
    for restoring a SQLite snapshot or inspecting a JSON delta.
    """
    record = _load_record(db, backup_id)
    if record.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Artefact was not completed")

    path = backup_service._backup_dir() / record.filename
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artefact file missing from backup directory")

    db.add(
        BackupAuditEvent(
            backup_id=int(record.id),
            actor_id=user.id,
            action="downloaded",
            detail=f"{record.filename} ({format})",
        )
    )
    db.commit()

    blob = path.read_bytes()
    if format == "encrypted":
        headers = {
            "Content-Disposition": f'attachment; filename="{record.filename}"',
            "X-Backup-SHA256": record.sha256 or "",
            "X-Backup-MD5": record.md5 or "",
        }
        return Response(content=blob, media_type="application/octet-stream", headers=headers)
    if format == "decrypted":
        try:
            plaintext = decrypt_bytes(blob)
        except ValueError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Decryption failed: {exc}")
        db.add(
            BackupAuditEvent(
                backup_id=int(record.id),
                actor_id=user.id,
                action="decrypted_download",
                detail=f"{record.filename} opened server-side (AES-256-GCM)",
            )
        )
        db.commit()

        inner_name = record.filename.replace(".nesbak", ".bin")
        if record.kind == "json_delta":
            # Deltas are plain JSON — return them directly for inspection.
            try:
                parsed = json.loads(plaintext)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                return StreamingResponse(
                    iter([plaintext]),
                    media_type="application/json",
                    headers={
                        "Content-Disposition": f'attachment; filename="{record.filename.replace(".nesbak", ".json")}"'
                    },
                )
        return Response(
            content=plaintext,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{inner_name}"'},
        )
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "format must be 'encrypted' or 'decrypted'")


def _load_record(db: Session, backup_id: int) -> BackupRecord:
    record = db.get(BackupRecord, backup_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Backup not found")
    return record


def _emit_backup_event(record: BackupRecord) -> None:
    from app.core.ws import manager as websocket_manager

    websocket_manager.broadcast_sync(
        "backup_completed",
        {
            "backup_id": int(record.id),
            "kind": record.kind,
            "status": record.status,
            "size_bytes": int(record.size_bytes or 0),
            "sha256": record.sha256,
        },
    )

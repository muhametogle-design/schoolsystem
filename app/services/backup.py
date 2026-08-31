"""Module 4 — Automated encrypted backups.

Pipeline
--------
1. **Change capture** — database triggers (installed here for the SQLite tier,
   ``sql/004_ops_modules.sql`` for PostgreSQL) append every INSERT/UPDATE/
   DELETE on the academic/operational core tables to ``data_change_log``.
2. **Midnight export** — the scheduler fires ``run_scheduled_backup`` at
   ``settings.backup_time`` (default 00:00 platform timezone):

   * ``full_snapshot`` — an online SQLite backup API snapshot of the whole
     database (``sqlite3.Connection.backup``; safe under live traffic/WAL);
   * ``json_delta``    — every ``data_change_log`` row newer than the last
     export's high-water mark, exported as structured JSON.

3. **Encryption at rest** — every artefact is sealed with **AES-256-GCM**
   (random 96-bit nonce, scrypt-derived key). The container format is::

       NESBK1\\n                      (magic)
       {"v":1,...}\\n                 (JSON header incl. nonce + KDF params)
       <ciphertext || 16-byte GCM tag>

4. **Integrity** — SHA-256 and MD5 digests are computed over the *encrypted*
   bytes and stored on ``backup_records``; downloads re-verify them and every
   action lands in the ``backup_audit_events`` admin trail.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import sqlite3
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import IS_SQLITE
from app.models import BackupAuditEvent, BackupRecord, DataChangeLog

logger = logging.getLogger("services.backup")

MAGIC = b"NESBK1\n"
#: Tables whose row changes feed the JSON delta export. The same list drives
#: trigger generation, so keeping it here keeps the two in lockstep.
TRACKED_TABLES = (
    "private_schools",
    "users",
    "school_classes",
    "subjects",
    "teaching_assignments",
    "students",
    "live_attendance",
    "daily_submission_logs",
    "student_grades",
    "exam_submission_events",
    "student_invoices",
    "payment_transactions",
    "tuition_rates",
    "teacher_absences",
    "substitution_assignments",
    "timetable_slots",
    "syllabus_plans",
    "syllabus_progress_entries",
    "biometric_credentials",
    "biometric_verification_logs",
)

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------


def key_source() -> str:
    """Where the AES-256 key comes from (surfaced in the admin config card)."""
    return "env:BACKUP_ENCRYPTION_KEY" if settings.backup_encryption_key else "derived:JWT_SECRET_KEY (demo)"


def _derive_key(salt: bytes) -> bytes:
    """Derive the 256-bit file key with scrypt from the configured secret."""
    secret = settings.backup_encryption_key or settings.jwt_secret_key
    kdf = Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(secret.encode("utf-8"))


def key_fingerprint() -> str:
    """Stable, non-secret identifier of the active key material."""
    digest = hashlib.sha256(
        ("bkp:" + (settings.backup_encryption_key or settings.jwt_secret_key)).encode()
    ).hexdigest()
    return digest[:16]


# ---------------------------------------------------------------------------
# AES-256-GCM container
# ---------------------------------------------------------------------------


def encrypt_bytes(plaintext: bytes) -> bytes:
    """Seal ``plaintext`` into the self-describing NESBK1 container."""
    salt = os.urandom(16)
    nonce = os.urandom(12)
    header = {
        "v": 1,
        "encryption": "AES-256-GCM",
        "kdf": {"algo": "scrypt", "salt": salt.hex(), "n": _SCRYPT_N, "r": _SCRYPT_R, "p": _SCRYPT_P},
        "nonce": nonce.hex(),
        "created": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    key = _derive_key(salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, MAGIC + header_bytes)
    return MAGIC + header_bytes + b"\n" + ciphertext


def decrypt_bytes(blob: bytes) -> bytes:
    """Open an NESBK1 container; raises ValueError on tamper/bad key."""
    if not blob.startswith(MAGIC):
        raise ValueError("Not a schoolsystem backup container (bad magic)")
    rest = blob[len(MAGIC):]
    header_end = rest.find(b"\n")
    if header_end < 0:
        raise ValueError("Corrupt backup container (missing header terminator)")
    header = json.loads(rest[:header_end].decode("utf-8"))
    kdf = header["kdf"]
    salt = bytes.fromhex(kdf["salt"])
    nonce = bytes.fromhex(header["nonce"])
    if header.get("encryption") != "AES-256-GCM":
        raise ValueError(f"Unsupported backup encryption: {header.get('encryption')}")

    key = _derive_key(salt)
    try:
        return AESGCM(key).decrypt(nonce, rest[header_end + 1:], MAGIC + rest[:header_end])
    except InvalidTag as exc:
        # A wrong key or an edited ciphertext both surface as authentication
        # failure; normalise to ValueError so callers get one contract.
        raise ValueError(
            "Backup authentication failed — wrong key or tampered artefact"
        ) from exc


def file_digests(path: Path) -> tuple[str, str]:
    """SHA-256 + MD5 over the file bytes (the encrypted container)."""
    sha = hashlib.sha256()
    md5 = hashlib.md5()  # noqa: S324 — legacy integrity mirror required by spec
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            sha.update(chunk)
            md5.update(chunk)
    return sha.hexdigest(), md5.hexdigest()


# ---------------------------------------------------------------------------
# Trigger installation (SQLite tier)
# ---------------------------------------------------------------------------


def _quote_sql_value(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _trigger_statements(table_name: str, columns: list[str]) -> list[str]:
    """Build AFTER INSERT/UPDATE/DELETE triggers writing JSON row payloads."""
    json_new = ", ".join(
        f"{_quote_sql_value(col)}, NEW.{_quote_ident(col)}" for col in columns
    )
    json_old = ", ".join(
        f"{_quote_sql_value(col)}, OLD.{_quote_ident(col)}" for col in columns
    )
    base = f"schoolsystem_clg_{table_name}"
    return [
        f"""
        CREATE TRIGGER IF NOT EXISTS {base}_ins AFTER INSERT ON {_quote_ident(table_name)}
        BEGIN
            INSERT INTO data_change_log (table_name, row_pk, operation, payload)
            VALUES ({_quote_sql_value(table_name)}, CAST(NEW.{_quote_ident(columns[0])} AS TEXT), 'I',
                    json_object({json_new}));
        END;
        """,
        f"""
        CREATE TRIGGER IF NOT EXISTS {base}_upd AFTER UPDATE ON {_quote_ident(table_name)}
        BEGIN
            INSERT INTO data_change_log (table_name, row_pk, operation, payload)
            VALUES ({_quote_sql_value(table_name)}, CAST(NEW.{_quote_ident(columns[0])} AS TEXT), 'U',
                    json_object({json_new}));
        END;
        """,
        f"""
        CREATE TRIGGER IF NOT EXISTS {base}_del AFTER DELETE ON {_quote_ident(table_name)}
        BEGIN
            INSERT INTO data_change_log (table_name, row_pk, operation, payload)
            VALUES ({_quote_sql_value(table_name)}, CAST(OLD.{_quote_ident(columns[0])} AS TEXT), 'D',
                    json_object({json_old}));
        END;
        """,
    ]


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def install_sqlite_change_triggers(connection) -> None:
    """Idempotently create the data_change_log triggers from ORM metadata.

    Called by ``init_db`` for the SQLite tier. Column lists come straight from
    the SQLAlchemy metadata, so new columns keep the delta export complete.
    """
    from app.models import Base

    if not _table_exists(connection, "data_change_log"):
        return

    for table_name in TRACKED_TABLES:
        model_table = Base.metadata.tables.get(table_name)
        if model_table is None or not _table_exists(connection, table_name):
            continue
        columns = [col.name for col in model_table.columns]
        if not columns:
            continue
        for statement in _trigger_statements(table_name, columns):
            connection.exec_driver_sql(statement)


def _table_exists(connection, table: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Backup production
# ---------------------------------------------------------------------------


def _backup_dir() -> Path:
    path = Path(settings.backup_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _database_row_counts(db: Session) -> dict[str, int]:
    from app.models import Base

    counts: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        try:
            counts[table.name] = int(
                db.execute(select(text(f"COUNT(*) FROM {_quote_ident(table.name)}"))).scalar_one()
            )
        except Exception:  # pragma: no cover — a dropped table must not abort a backup
            continue
    return counts


def _last_delta_high_water(db: Session) -> int:
    """High-water mark for the next JSON delta.

    Deltas chain from the latest completed artefact of ANY kind: the last
    delta if one exists, otherwise the last full snapshot (whose
    ``last_change_id`` froze the change-log head at snapshot time). This makes
    the first delta of an estate purely post-snapshot changes.
    """
    last_delta = db.execute(
        select(BackupRecord.last_change_id)
        .where(BackupRecord.kind == "json_delta", BackupRecord.status == "completed")
        .order_by(BackupRecord.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if last_delta is not None:
        return int(last_delta)
    snapshot_head = db.execute(
        select(BackupRecord.last_change_id)
        .where(BackupRecord.kind == "full_snapshot", BackupRecord.status == "completed")
        .order_by(BackupRecord.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return int(snapshot_head) if snapshot_head is not None else 0


def _export_sqlite_snapshot(target: Path) -> None:
    """Online snapshot of the SQLite database file (WAL-safe)."""
    db_path = settings.database_url.split("sqlite:///", 1)[-1]
    source = sqlite3.connect(db_path)
    try:
        destination = sqlite3.connect(str(target))
        try:
            with destination:
                source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


def _export_json_delta(db: Session, since_id: int) -> tuple[str, int, int]:
    """Serialise new change-log rows; returns (json, row_count, max_id)."""
    rows = db.execute(
        select(DataChangeLog).where(DataChangeLog.id > since_id).order_by(DataChangeLog.id)
    ).scalars().all()
    payload = {
        "format": "schoolsystem-json-delta",
        "version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "since_change_id": since_id,
        "rows": [
            {
                "change_id": int(row.id),
                "table": row.table_name,
                "pk": row.row_pk,
                "operation": row.operation,
                "changed_at": row.changed_at.isoformat() if row.changed_at else None,
                "payload": json.loads(row.payload) if row.payload else None,
            }
            for row in rows
        ],
    }
    max_id = int(rows[-1].id) if rows else since_id
    return json.dumps(payload, indent=2), len(rows), max_id


def _purge_expired(db: Session) -> int:
    cutoff = dt.datetime.now() - dt.timedelta(days=max(1, settings.backup_retention_days))
    stale = db.execute(
        select(BackupRecord).where(BackupRecord.created_at < cutoff, BackupRecord.status == "completed")
    ).scalars().all()
    removed = 0
    for record in stale:
        path = _backup_dir() / record.filename
        if path.exists():
            path.unlink(missing_ok=True)
        db.add(
            BackupAuditEvent(
                backup_id=None,
                action="purged",
                detail=f"{record.filename} removed after {settings.backup_retention_days}d retention",
            )
        )
        db.delete(record)
        removed += 1
    return removed


def create_backup(
    db: Session, *, kind: str = "auto", triggered_by: str = "manual", actor_id: int | None = None
) -> BackupRecord:
    """Produce, encrypt, hash and register one backup artefact."""
    started = dt.datetime.now()
    if kind == "auto":
        kind = "full_snapshot" if IS_SQLITE else "json_delta"

    timestamp = started.strftime("%Y%m%d-%H%M%S")
    suffix = "snapshot" if kind == "full_snapshot" else "delta"
    # Microsecond-resolution artefacts can share a wall-clock second (manual
    # + scheduled runs), so a short random tail keeps filenames unique.
    filename = f"schoolsystem-{suffix}-{timestamp}-{os.urandom(3).hex()}.nesbak"
    final_path = _backup_dir() / filename

    record = BackupRecord(
        filename=filename,
        kind=kind,
        triggered_by=triggered_by,
        status="failed",
        encrypted=True,
        encryption="AES-256-GCM",
    )
    try:
        with tempfile.TemporaryDirectory(prefix="nesbk-") as tmp:
            tmp_plaintext = Path(tmp) / "payload.bin"
            if kind == "full_snapshot":
                _export_sqlite_snapshot(tmp_plaintext)
                # Freeze the change-log head so the NEXT delta exports exactly
                # what changed after this baseline snapshot.
                head = db.execute(select(func.max(DataChangeLog.id))).scalar_one()
                record.last_change_id = int(head) if head is not None else 0
                record.delta_rows = None
            else:
                since = _last_delta_high_water(db)
                payload, row_count, max_id = _export_json_delta(db, since)
                tmp_plaintext.write_text(payload, encoding="utf-8")
                record.delta_rows = row_count
                record.last_change_id = max_id

            sealed = encrypt_bytes(tmp_plaintext.read_bytes())
            final_path.write_bytes(sealed)

        sha_hex, md5_hex = file_digests(final_path)
        record.size_bytes = final_path.stat().st_size
        record.sha256 = sha_hex
        record.md5 = md5_hex
        record.row_counts = json.dumps(_database_row_counts(db))
        record.status = "completed"
        record.duration_ms = int((dt.datetime.now() - started).total_seconds() * 1000)
        db.add(record)
        db.flush()
        db.add(
            BackupAuditEvent(
                backup_id=int(record.id),
                actor_id=actor_id,
                action="created",
                detail=(
                    f"{kind} sealed with AES-256-GCM ({record.size_bytes} bytes, "
                    f"sha256 {sha_hex[:12]}…, {triggered_by})"
                ),
            )
        )
        removed = _purge_expired(db)
        if removed:
            logger.info("Retention purge removed %d expired backup(s)", removed)
        db.commit()
        logger.info("Backup complete: %s (%s)", filename, record.status)
        return record
    except Exception as exc:
        db.rollback()
        logger.exception("Backup failed")
        # Re-register the failure so the audit trail shows the attempt.
        failed = BackupRecord(
            filename=filename,
            kind=kind,
            triggered_by=triggered_by,
            status="failed",
            encrypted=True,
            encryption="AES-256-GCM",
            error=str(exc)[:500],
            duration_ms=int((dt.datetime.now() - started).total_seconds() * 1000),
        )
        db.add(failed)
        db.add(
            BackupAuditEvent(
                backup_id=None,
                actor_id=actor_id,
                action="failed",
                detail=f"{kind} failed: {exc}",
            )
        )
        db.commit()
        raise


def verify_backup(db: Session, record: BackupRecord, actor_id: int | None = None) -> dict:
    """Recompute the stored digests from disk and audit the verdict."""
    path = _backup_dir() / record.filename
    if not path.exists():
        db.add(
            BackupAuditEvent(
                backup_id=int(record.id), actor_id=actor_id, action="verify_failed",
                detail="Artefact missing on disk",
            )
        )
        db.commit()
        return {"verified": False, "reason": "missing_file"}

    sha_hex, md5_hex = file_digests(path)
    ok = sha_hex == record.sha256 and md5_hex == record.md5
    db.add(
        BackupAuditEvent(
            backup_id=int(record.id),
            actor_id=actor_id,
            action="verified" if ok else "verify_failed",
            detail=f"sha256 {'match' if ok else 'MISMATCH'} ({sha_hex[:12]}…)",
        )
    )
    db.commit()
    return {
        "verified": ok,
        "sha256": sha_hex,
        "md5": md5_hex,
        "stored_sha256": record.sha256,
        "stored_md5": record.md5,
        "reason": None if ok else "hash_mismatch",
    }


def run_scheduled_backup() -> BackupRecord:
    """Midnight worker entry point (own session, state-admin scope)."""
    from app.core.db import SessionLocal, set_rls_context

    with SessionLocal() as session:
        if not IS_SQLITE:
            set_rls_context(session, school_id=None, role="state_admin")
        return create_backup(session, kind="auto", triggered_by="scheduled")


# ---------------------------------------------------------------------------
# Serialisation for the admin API
# ---------------------------------------------------------------------------


def record_payload(record: BackupRecord) -> dict:
    return {
        "id": int(record.id),
        "filename": record.filename,
        "kind": record.kind,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "size_bytes": int(record.size_bytes or 0),
        "sha256": record.sha256,
        "md5": record.md5,
        "encrypted": bool(record.encrypted),
        "encryption": record.encryption,
        "status": record.status,
        "duration_ms": record.duration_ms,
        "triggered_by": record.triggered_by,
        "delta_rows": record.delta_rows,
        "last_change_id": record.last_change_id,
        "row_counts": json.loads(record.row_counts) if record.row_counts else None,
        "error": record.error,
    }


def audit_payload(event: BackupAuditEvent) -> dict:
    return {
        "id": int(event.id),
        "backup_id": int(event.backup_id) if event.backup_id else None,
        "actor_id": int(event.actor_id) if event.actor_id else None,
        "action": event.action,
        "detail": event.detail,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def hashes_with_header(blob: bytes) -> tuple[dict, bytes]:
    """Split a container into (header, plaintext payload)."""
    header = json.loads(blob[len(MAGIC):].split(b"\n", 1)[0].decode("utf-8"))
    return header, decrypt_bytes(blob)

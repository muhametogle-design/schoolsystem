"""Tests for the encrypted backup pipeline (Module 4)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.backup import MAGIC, create_backup, decrypt_bytes, encrypt_bytes


def _state_admin(client: TestClient) -> dict:
    res = client.post(
        "/api/auth/login",
        json={"email": "stateadmin@education.gov", "password": "StateAdmin@2026"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _manager(client: TestClient) -> dict:
    res = client.post(
        "/api/auth/login",
        json={"email": "manager@nugaal.edu.so", "password": "School@2026"},
    )
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# --- unit-level crypto -------------------------------------------------------


def test_aes_roundtrip_and_tamper_detection():
    blob = encrypt_bytes(b"estate payload \x00\x01")
    assert blob.startswith(MAGIC)
    assert decrypt_bytes(blob) == b"estate payload \x00\x01"

    # Flip one ciphertext byte — GCM authentication must reject it.
    tampered = bytearray(blob)
    tampered[-1] ^= 0xFF
    with pytest.raises(ValueError):
        decrypt_bytes(bytes(tampered))


def test_containers_use_unique_nonces():
    a = encrypt_bytes(b"same payload")
    b = encrypt_bytes(b"same payload")
    assert a != b, "nonce reuse would be catastrophic"


# --- API pipeline ------------------------------------------------------------


def test_config_endpoint_reports_schedule_and_encryption(client):
    headers = _state_admin(client)
    res = client.get("/api/v1/admin/backups", headers=headers)
    assert res.status_code == 200
    config = res.json()["config"]
    assert config["schedule"] == settings.backup_time == "00:00"
    assert "AES-256-GCM" in config["encryption"]
    assert config["hashes"] == ["SHA-256", "MD5"]
    assert config["key_fingerprint"]


def test_manual_full_snapshot_is_encrypted_with_hashes(client):
    headers = _state_admin(client)
    res = client.post(
        "/api/v1/admin/backups/run", headers=headers, json={"kind": "full_snapshot"}
    )
    assert res.status_code == 201, res.text
    record = res.json()["backup"]

    assert record["kind"] == "full_snapshot"
    assert record["status"] == "completed"
    assert record["encrypted"] is True
    assert record["encryption"] == "AES-256-GCM"
    assert len(record["sha256"]) == 64
    assert len(record["md5"]) == 32
    assert record["size_bytes"] > 0

    # The artefact on disk is a sealed container, not plaintext SQLite.
    path = Path(settings.backup_dir) / record["filename"]
    assert path.exists()
    raw = path.read_bytes()
    assert raw.startswith(MAGIC)
    assert b"SQLite format 3" not in raw[:200], "snapshot must not be stored in plaintext"
    assert decrypt_bytes(raw)[:16] == b"SQLite format 3\x00"


def test_verify_recomputes_digests_and_audits(client):
    headers = _state_admin(client)
    created = client.post(
        "/api/v1/admin/backups/run", headers=headers, json={"kind": "full_snapshot"}
    ).json()["backup"]

    verified = client.get(f"/api/v1/admin/backups/{created['id']}/verify", headers=headers)
    assert verified.status_code == 200
    body = verified.json()
    assert body["verified"] is True
    assert body["sha256"] == created["sha256"]
    assert body["md5"] == created["md5"]

    audit = client.get("/api/v1/admin/backups/audit", headers=headers).json()["events"]
    actions = [event["action"] for event in audit]
    assert "created" in actions and "verified" in actions
    created_events = [e for e in audit if e["action"] == "created"]
    assert created_events and "scheduled" not in created_events[0]["detail"]


def test_json_delta_captures_only_new_changes(client):
    headers = _state_admin(client)

    # Baseline: a delta now (empty change log after seed baseline trim).
    first = client.post(
        "/api/v1/admin/backups/run", headers=headers, json={"kind": "json_delta"}
    ).json()["backup"]
    assert first["kind"] == "json_delta"

    # Live mutation: log an absence through the tenant API.
    manager = _manager(client)
    today = dt.date.today().isoformat()
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        from app.models import TimetableSlot

        slot = db.query(TimetableSlot).filter_by(school_id=3, day_of_week=dt.date.today().weekday()).first()
        teacher_id = slot.teacher_id
    logged = client.post(
        "/api/v1/school/absences",
        headers=manager,
        json={"teacher_id": teacher_id, "absence_date": today, "reason": "delta drill"},
    )
    assert logged.status_code == 201

    second = client.post(
        "/api/v1/admin/backups/run", headers=headers, json={"kind": "json_delta"}
    )
    assert second.status_code == 201
    delta = second.json()["backup"]
    assert (delta["delta_rows"] or 0) >= 1

    # The decrypted delta is inspectable JSON containing the change rows.
    download = client.get(
        f"/api/v1/admin/backups/{delta['id']}/download?format=decrypted", headers=headers
    )
    assert download.status_code == 200
    payload = download.json()
    assert payload["format"] == "schoolsystem-json-delta"
    tables = {row["table"] for row in payload["rows"]}
    assert "teacher_absences" in tables


def test_encrypted_download_streams_container_with_headers(client):
    headers = _state_admin(client)
    created = client.post(
        "/api/v1/admin/backups/run", headers=headers, json={"kind": "full_snapshot"}
    ).json()["backup"]

    res = client.get(f"/api/v1/admin/backups/{created['id']}/download", headers=headers)
    assert res.status_code == 200
    assert res.content.startswith(MAGIC)
    assert res.headers["x-backup-sha256"] == created["sha256"]
    assert "attachment" in res.headers["content-disposition"]

    audit = client.get("/api/v1/admin/backups/audit", headers=headers).json()["events"]
    assert any(e["action"] == "downloaded" for e in audit)


def test_tenant_roles_cannot_reach_backup_administration(client):
    res = client.get("/api/v1/admin/backups", headers=_manager(client))
    assert res.status_code == 403
    res = client.post(
        "/api/v1/admin/backups/run", headers=_manager(client), json={"kind": "full_snapshot"}
    )
    assert res.status_code == 403


def test_failed_kind_rejected(client):
    headers = _state_admin(client)
    res = client.post(
        "/api/v1/admin/backups/run", headers=headers, json={"kind": "databomb"}
    )
    assert res.status_code == 422

"""Unit tests for the cryptographic record-locking engine."""

from __future__ import annotations

import uuid

from app.core.crypto_lock import (
    build_lock_digest,
    generate_keypair,
    payload_digest,
    verify_envelope,
    sign_envelope,
    canonical_bytes,
)
from app.services.locking import sign_for_dean


def test_canonical_serialisation_is_stable():
    a = {"b": 1, "a": [3, 2, 1], "z": {"x": 1}}
    b = {"a": [3, 2, 1], "b": 1, "z": {"x": 1}}
    assert canonical_bytes(a) == canonical_bytes(b)


def test_payload_digest_prunes_volatile_metadata():
    campus = uuid.uuid4()
    payload_a = {
        "student_id": str(campus),
        "status": "present",
        "submitted_at": "2026-01-01T00:00:00Z",
    }
    payload_b = {
        "student_id": str(campus),
        "status": "present",
        "submitted_at": "2026-01-02T00:00:00Z",
    }
    assert payload_digest(payload_a) == payload_digest(payload_b)


def test_round_trip_signature():
    private, public = generate_keypair()
    campus = uuid.uuid4()
    entity = uuid.uuid4()
    payload = {"status": "present", "student_id": str(campus)}
    digest = build_lock_digest(
        "attendance",
        entity,
        campus,
        payload_digest(payload),
        locked_by=str(uuid.uuid4()),
    )
    sig = sign_envelope(private, digest)
    assert verify_envelope(public, digest, sig) is True


def test_locked_payload_rejects_wrong_signature():
    private, public = generate_keypair()
    campus = uuid.uuid4()
    entity = uuid.uuid4()
    digest = build_lock_digest(
        "exam_sheet", entity, campus, payload_digest({"score": 80})
    )
    sig = sign_envelope(private, digest)
    tampered = build_lock_digest(
        "exam_sheet", entity, campus, payload_digest({"score": 99})
    )
    assert verify_envelope(public, tampered, sig) is False


def test_sign_for_dean_helper():
    private, _ = generate_keypair()
    campus = uuid.uuid4()
    entity = uuid.uuid4()
    sig = sign_for_dean(
        private,
        entity_type="payroll_entry",
        entity_id=entity,
        campus_id=campus,
        payload={"net": 50000},
        locked_by=uuid.uuid4(),
    )
    assert len(sig) == 64

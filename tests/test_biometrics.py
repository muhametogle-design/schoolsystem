"""Tests for biometric hardware management (Module 5, WebAuthn).

The suite ships a minimal authenticator simulator: it fabricates a P-256
credential, builds a CBOR attestation object (fmt=none), and produces ES256
assertions — exercising the exact same server-side verification path that real
fingerprint readers and smartcards drive from the browser.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import struct

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

RP_ID = "testserver"
ORIGIN = "http://testserver"


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64u_dec(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


# --- minimal CBOR encoder (test-side complement of the server decoder) ------


def _cbor_encode(value) -> bytes:
    if isinstance(value, bool):
        return b"\xf5" if value else b"\xf4"
    if value is None:
        return b"\xf6"
    if isinstance(value, int):
        if value >= 0:
            return _cbor_uint(value, 0)
        return _cbor_uint(-1 - value, 0x20)
    if isinstance(value, bytes):
        return _cbor_uint(len(value), 0x40) + value
    if isinstance(value, str):
        raw = value.encode()
        return _cbor_uint(len(raw), 0x60) + raw
    if isinstance(value, dict):
        out = _cbor_uint(len(value), 0xA0)
        for key, item in value.items():
            out += _cbor_encode(key) + _cbor_encode(item)
        return out
    raise TypeError(f"Unsupported CBOR type: {type(value)}")


def _cbor_uint(value: int, base: int) -> bytes:
    """``base`` is the pre-shifted initial byte (major type << 5)."""
    if value < 24:
        return bytes([base | value])
    if value < 0x100:
        return bytes([base | 24, value])
    if value < 0x10000:
        return bytes([base | 25]) + value.to_bytes(2, "big")
    return bytes([base | 26]) + value.to_bytes(4, "big")


class SimulatedReader:
    """A fake fingerprint reader: one credential, endless assertions."""

    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.counter = 5

    def _public_cose(self) -> dict:
        numbers = self.key.public_key().public_numbers()
        return {1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")}

    def _auth_data(self, *, attested: bool) -> bytes:
        flags = 0x45 if attested else 0x05  # UP | UV (| AT)
        data = hashlib.sha256(RP_ID.encode()).digest() + bytes([flags]) + struct.pack(">I", self.counter)
        if attested:
            cose = _cbor_encode(self._public_cose())
            data += b"\x00" * 16 + struct.pack(">H", len(self.credential_id)) + self.credential_id + cose
        return data

    def registration_response(self, challenge: str) -> dict:
        client_data = json.dumps(
            {"type": "webauthn.create", "challenge": challenge, "origin": ORIGIN}
        ).encode()
        attestation = _cbor_encode(
            {"fmt": "none", "attStmt": {}, "authData": self._auth_data(attested=True)}
        )
        return {
            "credential_id": _b64u(self.credential_id),
            "client_data_b64": _b64u(client_data),
            "attestation_object_b64": _b64u(attestation),
        }

    def assertion_response(self, challenge: str) -> dict:
        self.counter += 1
        client_data = json.dumps(
            {"type": "webauthn.get", "challenge": challenge, "origin": ORIGIN}
        ).encode()
        auth_data = self._auth_data(attested=False)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "credential_id": _b64u(self.credential_id),
            "client_data_b64": _b64u(client_data),
            "authenticator_data_b64": _b64u(auth_data),
            "signature_b64": _b64u(signature),
        }


def _manager(client: TestClient) -> dict:
    res = client.post(
        "/api/auth/login",
        json={"email": "manager@nugaal.edu.so", "password": "School@2026"},
    )
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _enroll(client: TestClient, headers: dict, owner_type: str, owner_id: int, method: str = "fingerprint") -> dict:
    reader = SimulatedReader()
    options = client.post(
        "/api/v1/school/biometrics/enroll/options",
        headers=headers,
        json={"owner_type": owner_type, "owner_id": owner_id, "method": method},
    )
    assert options.status_code == 200, options.text
    challenge = options.json()["publicKey"]["challenge"]
    response = reader.registration_response(challenge)
    verify = client.post(
        "/api/v1/school/biometrics/enroll/verify",
        headers=headers,
        json={
            "owner_type": owner_type,
            "owner_id": owner_id,
            "method": method,
            "expected_challenge": challenge,
            "transports": ["internal"],
            **response,
        },
    )
    assert verify.status_code == 201, verify.text
    return {"reader": reader, "credential": verify.json()["credential"]}


def _student(client: TestClient, headers: dict) -> dict:
    """First *not yet enrolled* student (tests share one seeded database)."""
    overview = client.get("/api/v1/school/biometrics/overview", headers=headers).json()
    for student in overview["students"]:
        if student["status"] == "Not enrolled":
            return student
    raise AssertionError("every seeded student is already enrolled — extend the roster or reset")


def test_enrollment_registers_credential(client):
    headers = _manager(client)
    student = _student(client, headers)
    assert student["status"] == "Not enrolled"

    enrollment = _enroll(client, headers, "student", student["owner_id"])
    assert enrollment["credential"]["status"] == "active"
    assert enrollment["credential"]["method"] == "platform"  # internal transport

    overview = client.get("/api/v1/school/biometrics/overview", headers=headers).json()
    row = next(s for s in overview["students"] if s["owner_id"] == student["owner_id"])
    assert row["status"] == "Enrolled"
    assert overview["counts"]["students_enrolled"] >= 1


def test_exam_hall_entry_verification_flow(client):
    headers = _manager(client)
    student = _student(client, headers)
    _enroll(client, headers, "student", student["owner_id"])

    enrollment = _enroll(client, headers, "student", student["owner_id"], method="fingerprint")
    reader = enrollment["reader"]

    options = client.post(
        "/api/v1/school/biometrics/verify/options",
        headers=headers,
        json={
            "purpose": "exam_hall_entry",
            "owner_type": "student",
            "identifier": student["identifier"],
        },
    )
    assert options.status_code == 200, options.text
    challenge = options.json()["publicKey"]["challenge"]
    assertion = reader.assertion_response(challenge)
    complete = client.post(
        "/api/v1/school/biometrics/verify/complete",
        headers=headers,
        json={
            "purpose": "exam_hall_entry",
            "owner_type": "student",
            "owner_id": student["owner_id"],
            "expected_challenge": challenge,
            **assertion,
        },
    )
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["result"] == "success"
    assert body["purpose"] == "exam_hall_entry"
    assert body["verified_at"]

    logs = client.get(
        "/api/v1/school/biometrics/verifications?purpose=exam_hall_entry", headers=headers
    ).json()["verifications"]
    assert logs[0]["result"] == "success"
    assert logs[0]["person_label"]


def test_replayed_counter_is_rejected_as_clone(client):
    headers = _manager(client)
    student = _student(client, headers)
    enrollment = _enroll(client, headers, "student", student["owner_id"])
    reader = enrollment["reader"]

    def station() -> str:
        res = client.post(
            "/api/v1/school/biometrics/verify/options",
            headers=headers,
            json={
                "purpose": "exam_hall_entry",
                "owner_type": "student",
                "identifier": student["identifier"],
            },
        )
        assert res.status_code == 200
        return res.json()["publicKey"]["challenge"]

    challenge = station()
    assertion = reader.assertion_response(challenge)
    ok = client.post(
        "/api/v1/school/biometrics/verify/complete",
        headers=headers,
        json={
            "purpose": "exam_hall_entry",
            "owner_type": "student",
            "owner_id": student["owner_id"],
            "expected_challenge": challenge,
            **assertion,
        },
    )
    assert ok.status_code == 200, ok.text

    # Replay the exact same assertion: the challenge is single-use, and the
    # frozen signature counter would independently trip clone detection.
    replay = client.post(
        "/api/v1/school/biometrics/verify/complete",
        headers=headers,
        json={
            "purpose": "exam_hall_entry",
            "owner_type": "student",
            "owner_id": student["owner_id"],
            "expected_challenge": challenge,
            **assertion,
        },
    )
    assert replay.status_code == 400
    assert "challenge" in replay.json()["detail"].lower()


def test_rescan_revokes_and_reissues_enrollment(client):
    headers = _manager(client)
    staff = client.get("/api/v1/school/biometrics/overview", headers=headers).json()["staff"][0]
    enrollment = _enroll(client, headers, "staff", staff["owner_id"], method="smartcard")
    credential_id = enrollment["credential"]["id"]

    rescan = client.post(
        f"/api/v1/school/biometrics/credentials/{credential_id}/rescan", headers=headers
    )
    assert rescan.status_code == 200, rescan.text
    body = rescan.json()
    assert body["revoked"]["status"] == "revoked"
    assert "publicKey" in body["re_enroll"]

    overview = client.get("/api/v1/school/biometrics/overview", headers=headers).json()
    row = next(s for s in overview["staff"] if s["owner_id"] == staff["owner_id"])
    assert row["status"] == "Revoked"


def test_revoke_blocks_verification(client):
    headers = _manager(client)
    student = _student(client, headers)
    enrollment = _enroll(client, headers, "student", student["owner_id"])
    credential_pk_id = enrollment["credential"]["id"]

    revoke = client.delete(
        f"/api/v1/school/biometrics/credentials/{credential_pk_id}", headers=headers
    )
    assert revoke.status_code == 200

    station = client.post(
        "/api/v1/school/biometrics/verify/options",
        headers=headers,
        json={
            "purpose": "staff_attendance",
            "owner_type": "student",
            "identifier": student["identifier"],
        },
    )
    assert station.status_code == 409  # no active credentials remain
    assert "enroll first" in station.json()["detail"]


def test_verification_requires_prior_enrollment(client):
    headers = _manager(client)
    student = _student(client, headers)
    res = client.post(
        "/api/v1/school/biometrics/verify/options",
        headers=headers,
        json={
            "purpose": "exam_hall_entry",
            "owner_type": "student",
            "identifier": student["identifier"],
        },
    )
    assert res.status_code == 409


def test_bad_attestation_rejected_and_logged(client):
    headers = _manager(client)
    student = _student(client, headers)
    options = client.post(
        "/api/v1/school/biometrics/enroll/options",
        headers=headers,
        json={"owner_type": "student", "owner_id": student["owner_id"]},
    )
    challenge = options.json()["publicKey"]["challenge"]
    bad = SimulatedReader().registration_response(challenge)
    bad["attestation_object_b64"] = _b64u(b"garbage")

    verify = client.post(
        "/api/v1/school/biometrics/enroll/verify",
        headers=headers,
        json={
            "owner_type": "student",
            "owner_id": student["owner_id"],
            "method": "fingerprint",
            "expected_challenge": challenge,
            "transports": ["internal"],
            **bad,
        },
    )
    assert verify.status_code == 400
    logs = client.get(
        "/api/v1/school/biometrics/verifications?result=failed", headers=headers
    ).json()["verifications"]
    assert any("Enrollment rejected" in entry["detail"] for entry in logs)


def test_tampered_assertion_signature_fails(client):
    headers = _manager(client)
    student = _student(client, headers)
    enrollment = _enroll(client, headers, "student", student["owner_id"])
    reader = enrollment["reader"]

    station = client.post(
        "/api/v1/school/biometrics/verify/options",
        headers=headers,
        json={
            "purpose": "staff_attendance",
            "owner_type": "student",
            "identifier": student["identifier"],
        },
    )
    challenge = station.json()["publicKey"]["challenge"]
    assertion = reader.assertion_response(challenge)
    raw = bytearray(_b64u_dec(assertion["signature_b64"]))
    raw[10] ^= 0xFF
    assertion["signature_b64"] = _b64u(bytes(raw))

    complete = client.post(
        "/api/v1/school/biometrics/verify/complete",
        headers=headers,
        json={
            "purpose": "staff_attendance",
            "owner_type": "student",
            "owner_id": student["owner_id"],
            "expected_challenge": challenge,
            **assertion,
        },
    )
    assert complete.status_code == 403
    assert "failed" in complete.json()["detail"].lower()


def test_state_role_firewalled(client, state_token):
    res = client.get(
        "/api/v1/school/biometrics/overview", headers={"Authorization": f"Bearer {state_token}"}
    )
    assert res.status_code == 403

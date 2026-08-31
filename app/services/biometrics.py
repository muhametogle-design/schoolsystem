"""Module 5 — Biometric hardware management (WebAuthn).

A self-contained WebAuthn Level-1 relying-party implementation:

* minimal deterministic **CBOR decoder** for attestation objects and COSE keys;
* registration ceremony (``webauthn.create``) with origin/RP-ID/UV checks;
* assertion ceremony (``webauthn.get``) verifying **ES256** and **RS256**
  signatures over ``authenticatorData || SHA-256(clientDataJSON)`` with
  signature-counter clone detection;
* credential lifecycle (enroll → verify → re-scan → revoke) plus the
  verification audit feed for exam-hall entry and staff attendance.

No third-party WebAuthn library is used — the cryptography primitives come
from ``cryptography`` (already a platform dependency via the backup module).
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import secrets
from dataclasses import dataclass
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BiometricCredential, BiometricVerificationLog

# --- CBOR -------------------------------------------------------------------
# Subset decoder covering everything WebAuthn attestation objects use:
# unsigned/negative ints, byte/text strings, arrays, maps, tags, bool/null.

_CBOR_MAJOR = lambda byte: byte >> 5  # noqa: E731
_CBOR_INFO = lambda byte: byte & 0x1F  # noqa: E731


class CBORError(ValueError):
    pass


def cbor_decode(data: bytes):
    """Decode the first CBOR item in ``data``; returns (value, bytes_consumed)."""
    if not data:
        raise CBORError("Empty CBOR input")
    value, offset = _cbor_item(data, 0)
    return value, offset


def cbor_decode_all(data: bytes):
    value, offset = cbor_decode(data)
    if offset != len(data):
        raise CBORError(f"Trailing bytes after CBOR item ({len(data) - offset})")
    return value


def _cbor_item(data: bytes, index: int):
    if index >= len(data):
        raise CBORError("Truncated CBOR")
    initial = data[index]
    major, info = _CBOR_MAJOR(initial), _CBOR_INFO(initial)
    index += 1

    if major == 0:
        value, index = _cbor_uint(data, index, info)
        return value, index
    if major == 1:
        value, index = _cbor_uint(data, index, info)
        return -1 - value, index
    if major == 2:  # byte string
        length, index = _cbor_uint(data, index, info)
        end = index + length
        if end > len(data):
            raise CBORError("Truncated byte string")
        return bytes(data[index:end]), end
    if major == 3:  # text string
        length, index = _cbor_uint(data, index, info)
        end = index + length
        if end > len(data):
            raise CBORError("Truncated text string")
        return data[index:end].decode("utf-8"), end
    if major == 4:  # array
        length, index = _cbor_uint(data, index, info)
        items = []
        for _ in range(length):
            value, index = _cbor_item(data, index)
            items.append(value)
        return items, index
    if major == 5:  # map
        length, index = _cbor_uint(data, index, info)
        result = {}
        for _ in range(length):
            key, index = _cbor_item(data, index)
            value, index = _cbor_item(data, index)
            result[key] = value
        return result, index
    if major == 6:  # tag — decode the tagged value directly
        _cbor_uint(data, index, info)
        return _cbor_item(data, index)
    if major == 7:
        if info == 20:
            return False, index
        if info == 21:
            return True, index
        if info == 22:
            return None, index
        if info == 27:  # float64
            end = index + 8
            if end > len(data):
                raise CBORError("Truncated float")
            import struct

            return struct.unpack(">d", data[index:end])[0], end
        raise CBORError(f"Unsupported simple value info={info}")
    raise CBORError(f"Unsupported CBOR major type {major}")


def _cbor_uint(data: bytes, index: int, info: int) -> tuple[int, int]:
    if info < 24:
        return info, index
    widths = {24: 1, 25: 2, 26: 4, 27: 8}
    if info not in widths:
        raise CBORError(f"Unsupported CBOR uint info={info}")
    width = widths[info]
    end = index + width
    if end > len(data):
        raise CBORError("Truncated uint")
    return int.from_bytes(data[index:end], "big"), end


# --- WebAuthn structures ----------------------------------------------------


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    padding_needed = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding_needed)


@dataclass
class WebAuthnContext:
    """Resolved per-request RP configuration."""

    rp_id: str
    origin: str
    rp_name: str


def resolve_context(request) -> WebAuthnContext:
    """Resolve the Relying Party ID and accepted origin from the request.

    ``auto`` mode derives both from the request host, so localhost, Tailscale,
    and preview hosts all work without configuration; production pins them via
    WEBAUTHN_RP_ID / WEBAUTHN_EXPECTED_ORIGINS.
    """
    from app.core.config import settings

    host = (request.url.hostname or "localhost").lower()
    rp_id = settings.webauthn_rp_id
    if not rp_id or rp_id == "auto":
        rp_id = host

    allowed = settings.webauthn_expected_origins
    if allowed == ["auto"]:
        origin = f"{request.url.scheme}://{request.url.netloc}"
    else:
        origin = allowed[0] if allowed else f"{request.url.scheme}://{request.url.netloc}"
    return WebAuthnContext(rp_id=rp_id, origin=origin, rp_name="NE-EMIS")


def _user_handle(owner_type: str, owner_id: int) -> bytes:
    return f"{owner_type}:{owner_id}".encode("utf-8")


def generate_registration_options(
    context: WebAuthnContext, *, owner_type: str, owner_id: int, owner_name: str, exclude: list[str]
) -> dict:
    challenge = secrets.token_bytes(32)
    return {
        "publicKey": {
            "challenge": b64url_encode(challenge),
            "rp": {"id": context.rp_id, "name": context.rp_name},
            "user": {
                "id": b64url_encode(_user_handle(owner_type, owner_id)),
                "name": owner_name,
                "displayName": owner_name,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},   # ES256
                {"type": "public-key", "alg": -257},  # RS256
            ],
            "timeout": 120_000,
            "attestation": "none",
            "excludeCredentials": [
                {"type": "public-key", "id": cred_id, "transports": ["internal", "usb", "nfc", "ble"]}
                for cred_id in exclude
            ],
            "authenticatorSelection": {
                "userVerification": "required",
                "residentKey": "preferred",
            },
        },
        # Echoed in the verify call; validated server-side, never trusted client-side.
        "challenge_hint": b64url_encode(hashlib.sha256(challenge).hexdigest().encode())[:16],
    }


@dataclass
class RegistrationResult:
    credential_id: str
    public_key_b64: str
    sign_count: int
    aaguid: str
    device_type: str
    transports: list[str]
    method_hint: str


def _parse_client_data(raw_b64: str, *, expected_type: str, expected_challenge: str, context: WebAuthnContext) -> dict:
    try:
        client = json.loads(b64url_decode(raw_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError("clientDataJSON is not valid JSON") from exc
    if client.get("type") != expected_type:
        raise ValueError(f"Unexpected ceremony type: {client.get('type')}")
    if client.get("challenge") != expected_challenge:
        raise ValueError("Challenge mismatch — possible replay")
    origin = str(client.get("origin", "")).rstrip("/")

    from app.core.config import settings

    pinned = settings.webauthn_expected_origins
    if pinned and pinned != ["auto"]:
        # Production: the accepted origins are pinned in configuration.
        if origin not in {o.rstrip("/") for o in pinned}:
            raise ValueError(f"Origin {origin} is not an accepted WebAuthn origin")
    else:
        # Auto mode: the ceremony must be addressed to this deployment's own origin.
        if not context.origin or origin != context.origin.rstrip("/"):
            raise ValueError(f"Origin {origin} does not match the relying-party origin")
    return client


def _parse_authenticator_data(auth_data: bytes) -> tuple[bytes, int, bool, dict | None]:
    """Returns (rp_id_hash, sign_count, user_verified, attested_credential|None)."""
    if len(auth_data) < 37:
        raise ValueError("authenticatorData too short")
    rp_id_hash = auth_data[:32]
    flags = auth_data[32]
    sign_count = int.from_bytes(auth_data[33:37], "big")
    user_present = bool(flags & 0x01)
    user_verified = bool(flags & 0x04)
    attested = None
    if flags & 0x40:  # AT — attested credential data included
        if len(auth_data) < 55 + 18:
            raise ValueError("Truncated attested credential data")
        aaguid = auth_data[37:53].hex()
        cred_id_len = int.from_bytes(auth_data[53:55], "big")
        end = 55 + cred_id_len
        if end > len(auth_data):
            raise ValueError("Credential ID overruns authenticatorData")
        credential_id = auth_data[55:end]
        cose_key, consumed = cbor_decode(auth_data[end:])
        attested = {
            "aaguid": aaguid,
            "credential_id": b64url_encode(credential_id),
            "cose_key": cose_key,
            # Raw canonical CBOR of the COSE key — this is what we persist.
            "cose_key_raw": auth_data[end : end + consumed],
            "consumed": end + consumed,
        }
    if not user_present:
        raise ValueError("Authenticator did not assert user presence")
    return rp_id_hash, sign_count, user_verified, attested


def _cose_to_public_key(cose: dict):
    """Convert a COSE key to a cryptography public key (EC2/ES256, RSA/RS256)."""
    kty = cose.get(1)
    alg = cose.get(3)
    if kty == 2 and alg == -7:  # EC2 + ES256
        if cose.get(-1) != 1:  # P-256
            raise ValueError("Only the P-256 curve is supported for ES256")
        x = cose.get(-2)
        y = cose.get(-3)
        if not isinstance(x, bytes) or not isinstance(y, bytes):
            raise ValueError("Invalid EC2 coordinates")
        numbers = ec.EllipticCurvePublicNumbers(
            int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
        )
        return numbers.public_key()
    if kty == 3 and alg == -257:  # RSA + RS256
        n = cose.get(-1)
        e = cose.get(-2)
        if not isinstance(n, bytes) or not isinstance(e, bytes):
            raise ValueError("Invalid RSA parameters")
        return rsa.RSAPublicNumbers(int.from_bytes(e, "big"), int.from_bytes(n, "big")).public_key()
    raise ValueError(f"Unsupported COSE key type/algorithm: kty={kty} alg={alg}")


def verify_registration(
    context: WebAuthnContext,
    *,
    credential_b64: str | None = None,
    client_data_b64: str = "",
    attestation_object_b64: str = "",
    expected_challenge: str = "",
    transports: list[str] | None = None,
) -> RegistrationResult:
    """Validate a ``navigator.credentials.create()`` response server-side."""
    client = _parse_client_data(
        client_data_b64,
        expected_type="webauthn.create",
        expected_challenge=expected_challenge,
        context=context,
    )

    attestation = cbor_decode_all(b64url_decode(attestation_object_b64))
    fmt = attestation.get("fmt")
    auth_data = attestation.get("authData")
    if not isinstance(auth_data, bytes):
        raise ValueError("Attestation object lacks binary authData")
    if fmt not in ("none", "packed", "self"):  # accepted attestation policies
        raise ValueError(f"Attestation format '{fmt}' is not accepted")

    rp_id_hash, sign_count, user_verified, attested = _parse_authenticator_data(auth_data)
    if rp_id_hash != hashlib.sha256(context.rp_id.encode("utf-8")).digest():
        raise ValueError("RP ID hash mismatch")
    if not user_verified:
        raise ValueError("User verification (fingerprint/PIN) is required")

    if attested is None:
        raise ValueError("No attested credential data in registration response")

    method_hint = "platform"
    if transports and any(t in ("usb", "nfc", "ble") for t in transports):
        method_hint = "smartcard" if "smartcard" in transports or "nfc" in transports else "usb_key"

    return RegistrationResult(
        credential_id=attested["credential_id"],
        # The COSE key is stored exactly as the authenticator produced it.
        public_key_b64=base64.b64encode(attested["cose_key_raw"]).decode("ascii"),
        sign_count=sign_count,
        aaguid=attested["aaguid"],
        device_type=fmt or "none",
        transports=transports or ["internal"],
        method_hint=method_hint,
    )


def generate_authentication_options(
    context: WebAuthnContext, *, challenge: bytes, allow_credential_ids: list[str]
) -> dict:
    return {
        "publicKey": {
            "challenge": b64url_encode(challenge),
            "rpId": context.rp_id,
            "timeout": 120_000,
            "userVerification": "required",
            "allowCredentials": [
                {"type": "public-key", "id": cred_id, "transports": ["internal", "usb", "nfc", "ble"]}
                for cred_id in allow_credential_ids
            ],
        }
    }


def verify_assertion(
    context: WebAuthnContext,
    *,
    credential: BiometricCredential,
    credential_b64: str,
    client_data_b64: str,
    authenticator_data_b64: str,
    signature_b64: str,
    expected_challenge: str,
) -> int:
    """Validate a ``navigator.credentials.get()`` assertion; returns new sign count."""
    import base64 as _b64

    client = _parse_client_data(
        client_data_b64,
        expected_type="webauthn.get",
        expected_challenge=expected_challenge,
        context=context,
    )
    if credential_b64 != credential.credential_id:
        raise ValueError("Assertion was signed by a different credential")

    auth_data = b64url_decode(authenticator_data_b64)
    signature = b64url_decode(signature_b64)
    rp_id_hash, sign_count, user_verified, _ = _parse_authenticator_data(auth_data)
    if rp_id_hash != hashlib.sha256(context.rp_id.encode("utf-8")).digest():
        raise ValueError("RP ID hash mismatch")
    if not user_verified:
        raise ValueError("User verification (fingerprint/PIN) is required")

    public_key = _cose_to_public_key(cbor_decode_all(_b64.b64decode(credential.public_key)))
    signed = auth_data + hashlib.sha256(b64url_decode(client_data_b64)).digest()
    try:
        if isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(signature, signed, ec.ECDSA(hashes.SHA256()))
        else:
            public_key.verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise ValueError("Signature verification failed") from exc

    # Clone detection: the counter must be monotonically non-decreasing and
    # should advance whenever the authenticator reports one.
    previous = int(credential.sign_count or 0)
    if sign_count != 0 and previous != 0 and sign_count <= previous:
        raise ValueError("Signature counter did not advance — possible cloned credential")
    return sign_count


# --- Tenant helpers ---------------------------------------------------------


def active_credentials(db: Session, *, owner_type: str, owner_id: int) -> list[BiometricCredential]:
    return list(
        db.execute(
            select(BiometricCredential).where(
                BiometricCredential.owner_type == owner_type,
                BiometricCredential.owner_id == owner_id,
                BiometricCredential.status == "active",
            )
        ).scalars().all()
    )


def log_verification(
    db: Session,
    *,
    school_id: int | None,
    owner_type: str | None,
    owner_id: int | None,
    purpose: str,
    result: str,
    credential_id: str | None,
    person_label: str | None,
    detail: str | None,
    operated_by: int | None,
) -> BiometricVerificationLog:
    entry = BiometricVerificationLog(
        school_id=school_id,
        owner_type=owner_type,
        owner_id=owner_id,
        purpose=purpose,
        result=result,
        credential_id=credential_id,
        person_label=person_label,
        detail=detail,
        verified_at=dt.datetime.now(),
        operated_by=operated_by,
    )
    db.add(entry)
    return entry

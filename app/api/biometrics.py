"""Module 5 API — biometric hardware management (WebAuthn).

Tenant-scoped enrollment and verification for students and teaching staff:

* ``/biometrics/overview`` — registration status roster + KPI counts;
* ``/biometrics/enroll/options|verify`` — the registration ceremony
  (fingerprint readers, smartcards, platform authenticators);
* ``/biometrics/verify/options|complete`` — the verification station for
  exam-hall entry and staff attendance, with timestamped audit logging;
* ``/biometrics/credentials/{id}/rescan`` — hardware re-scan (revoke + fresh
  enrollment options for the same person).

Verification history doubles as the exam-hall entry register and the staff
attendance biometric timesheet.
"""

from __future__ import annotations

import datetime as dt
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_school
from app.core.db import get_db
from app.core.ws import manager as websocket_manager
from app.models import (
    BiometricCredential,
    BiometricVerificationLog,
    SchoolClass,
    Student,
    User,
)
from app.schemas import (
    BiometricEnrollOptionsRequest,
    BiometricEnrollVerifyRequest,
    BiometricVerifyCompleteRequest,
    BiometricVerifyOptionsRequest,
)
from app.services import biometrics
from app.services.biometrics import WebAuthnContext

router = APIRouter(prefix="/api/v1/school/biometrics", tags=["biometrics"])

erp_write = require_school("school_manager", "teacher")
any_school_user = require_school()


# --- helpers ----------------------------------------------------------------


def _display_name(owner_type: str, owner) -> str:
    if owner is None:
        return "Unknown"
    name = f"{owner.first_name or ''} {owner.last_name or ''}".strip()
    return name or getattr(owner, "email", "Unknown")


def _resolve_owner(db: Session, school_id: int, owner_type: str, owner_id: int):
    if owner_type == "student":
        owner = db.execute(
            select(Student).where(Student.id == owner_id, Student.school_id == school_id)
        ).scalar_one_or_none()
    else:
        owner = db.execute(
            select(User).where(User.id == owner_id, User.school_id == school_id)
        ).scalar_one_or_none()
    if not owner:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{owner_type} not found in this school")
    return owner


def _resolve_by_identifier(db: Session, school_id: int, owner_type: str, identifier: str):
    identifier = identifier.strip()
    if owner_type == "student":
        owner = db.execute(
            select(Student).where(
                Student.school_id == school_id,
                (Student.roll_number == identifier) | (Student.national_student_id == identifier),
            )
        ).scalar_one_or_none()
    else:
        owner = db.execute(
            select(User).where(
                User.school_id == school_id,
                (User.email == identifier.lower()) | (User.staff_identifier == identifier),
            )
        ).scalar_one_or_none()
    if not owner:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No {owner_type} matches '{identifier}'")
    return owner


def _credential_payload(credential: BiometricCredential) -> dict:
    return {
        "id": int(credential.id),
        "credential_id": credential.credential_id,
        "owner_type": credential.owner_type,
        "owner_id": int(credential.owner_id),
        "method": credential.method,
        "label": credential.label,
        "transports": credential.transports.split(",") if credential.transports else [],
        "device_type": credential.device_type,
        "aaguid": credential.aaguid,
        "status": credential.status,
        "sign_count": int(credential.sign_count or 0),
        "created_at": credential.created_at.isoformat() if credential.created_at else None,
        "last_used_at": credential.last_used_at.isoformat() if credential.last_used_at else None,
        "revoked_at": credential.revoked_at.isoformat() if credential.revoked_at else None,
    }


def _log_payload(entry: BiometricVerificationLog) -> dict:
    return {
        "id": int(entry.id),
        "owner_type": entry.owner_type,
        "owner_id": int(entry.owner_id) if entry.owner_id else None,
        "person_label": entry.person_label,
        "purpose": entry.purpose,
        "result": entry.result,
        "credential_id": entry.credential_id,
        "detail": entry.detail,
        "verified_at": entry.verified_at.isoformat() if entry.verified_at else None,
    }


# --- overview ---------------------------------------------------------------


@router.get("/overview")
def overview(
    limit: int = 400,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Roster-wide biometric registration status for students and staff."""
    limit = max(1, min(limit, 1000))

    students = db.execute(
        select(Student).where(Student.school_id == user.school_id).order_by(Student.roll_number).limit(limit)
    ).scalars().all()
    staff = db.execute(
        select(User).where(
            User.school_id == user.school_id, User.role.in_(("teacher", "school_manager"))
        )
    ).scalars().all()

    credentials = db.execute(
        select(BiometricCredential).where(BiometricCredential.school_id == user.school_id)
    ).scalars().all()
    creds_by_owner: dict[tuple[str, int], list[BiometricCredential]] = {}
    for credential in credentials:
        creds_by_owner.setdefault((credential.owner_type, int(credential.owner_id)), []).append(credential)

    latest_logs: dict[tuple[str, int], BiometricVerificationLog] = {}
    for entry in db.execute(
        select(BiometricVerificationLog)
        .where(BiometricVerificationLog.school_id == user.school_id)
        .order_by(BiometricVerificationLog.verified_at.desc())
        .limit(500)
    ).scalars().all():
        key = (entry.owner_type or "", int(entry.owner_id or 0))
        latest_logs.setdefault(key, entry)

    def _person_row(owner_type: str, owner, meta: str | None) -> dict:
        creds = creds_by_owner.get((owner_type, int(owner.id)), [])
        active = [c for c in creds if c.status == "active"]
        last_log = latest_logs.get((owner_type, int(owner.id)))
        return {
            "owner_type": owner_type,
            "owner_id": int(owner.id),
            "name": _display_name(owner_type, owner),
            "identifier": owner.roll_number if owner_type == "student" else (owner.staff_identifier or owner.email),
            "meta": meta,
            "status": "Enrolled" if active else ("Revoked" if creds else "Not enrolled"),
            "credentials": [_credential_payload(c) for c in creds],
            "last_verification": last_log.verified_at.isoformat() if last_log else None,
            "last_verification_result": last_log.result if last_log else None,
            "last_purpose": last_log.purpose if last_log else None,
        }

    class_map = {
        int(c.id): c for c in db.execute(select(SchoolClass).where(SchoolClass.school_id == user.school_id)).scalars().all()
    }
    student_rows = [
        _person_row(
            "student",
            student,
            (
                f"{class_map[student.current_class_id].class_level} {class_map[student.current_class_id].class_stream}"
                if student.current_class_id in class_map
                else None
            ),
        )
        for student in students
    ]
    staff_rows = [
        _person_row(
            "staff",
            person,
            person.designation or ("School Manager" if person.role == "school_manager" else "Teacher"),
        )
        for person in staff
    ]

    today = dt.date.today()
    today_counts = {"success": 0, "failed": 0}
    for entry in db.execute(
        select(BiometricVerificationLog).where(
            BiometricVerificationLog.school_id == user.school_id,
            func.date(BiometricVerificationLog.verified_at) == today.isoformat(),
        )
    ).scalars().all():
        if entry.result == "success":
            today_counts["success"] += 1
        else:
            today_counts["failed"] += 1

    return {
        "students": student_rows,
        "staff": staff_rows,
        "counts": {
            "students_total": len(student_rows),
            "students_enrolled": sum(1 for row in student_rows if row["status"] == "Enrolled"),
            "staff_total": len(staff_rows),
            "staff_enrolled": sum(1 for row in staff_rows if row["status"] == "Enrolled"),
            "credentials_active": sum(1 for c in credentials if c.status == "active"),
            "verifications_today": today_counts,
        },
    }


@router.get("/verifications")
def verification_log(
    purpose: str | None = None,
    result: str | None = None,
    limit: int = 100,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Timestamped verification feed (exam-hall register / attendance audit)."""
    query = (
        select(BiometricVerificationLog)
        .where(BiometricVerificationLog.school_id == user.school_id)
        .order_by(BiometricVerificationLog.verified_at.desc(), BiometricVerificationLog.id.desc())
        .limit(max(1, min(int(limit), 500)))
    )
    if purpose:
        query = query.where(BiometricVerificationLog.purpose == purpose)
    if result:
        query = query.where(BiometricVerificationLog.result == result)
    entries = db.execute(query).scalars().all()
    return {"verifications": [_log_payload(entry) for entry in entries]}


# --- enrollment -------------------------------------------------------------


@router.post("/enroll/options")
def enroll_options(
    payload: BiometricEnrollOptionsRequest,
    request: Request,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    """Start a WebAuthn registration ceremony for one student or staff member."""
    context: WebAuthnContext = biometrics.resolve_context(request)
    owner = _resolve_owner(db, user.school_id, payload.owner_type, payload.owner_id)
    existing = db.execute(
        select(BiometricCredential).where(
            BiometricCredential.owner_type == payload.owner_type,
            BiometricCredential.owner_id == owner.id,
            BiometricCredential.status == "active",
        )
    ).scalars().all()
    owner_name = (
        _display_name("staff", owner)
        if payload.owner_type == "staff"
        else f"{owner.first_name} {owner.last_name} ({owner.roll_number})"
    )
    options = biometrics.generate_registration_options(
        context,
        owner_type=payload.owner_type,
        owner_id=int(owner.id),
        owner_name=owner_name,
        exclude=[c.credential_id for c in existing],
    )
    # The challenge is stored implicitly: the client echoes expected_challenge;
    # the server binds it to this owner in a signed-off single-use registry.
    _challenge_store.issue(options["publicKey"]["challenge"], context.origin)
    return {
        "owner": {"owner_type": payload.owner_type, "owner_id": int(owner.id), "name": owner_name},
        "method": payload.method,
        **options,
    }


@router.post("/enroll/verify", status_code=status.HTTP_201_CREATED)
def enroll_verify(
    payload: BiometricEnrollVerifyRequest,
    request: Request,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    """Verify the registration response and persist the new credential."""
    context = biometrics.resolve_context(request)
    if not _challenge_store.consume(payload.expected_challenge, payload.credential_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown or expired enrollment challenge")
    owner = _resolve_owner(db, user.school_id, payload.owner_type, payload.owner_id)

    try:
        result = biometrics.verify_registration(
            context,
            client_data_b64=payload.client_data_b64,
            attestation_object_b64=payload.attestation_object_b64,
            expected_challenge=payload.expected_challenge,
            transports=payload.transports,
        )
    except ValueError as exc:
        biometrics.log_verification(
            db,
            school_id=user.school_id,
            owner_type=payload.owner_type,
            owner_id=int(owner.id),
            purpose="enrollment_check",
            result="failed",
            credential_id=None,
            person_label=_display_name(payload.owner_type, owner),
            detail=f"Enrollment rejected: {exc}",
            operated_by=user.id,
        )
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Enrollment rejected: {exc}")

    duplicate = db.execute(
        select(BiometricCredential).where(BiometricCredential.credential_id == result.credential_id)
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, "This authenticator is already registered")

    method = payload.method if payload.method != "fingerprint" else result.method_hint
    credential = BiometricCredential(
        school_id=user.school_id,
        owner_type=payload.owner_type,
        owner_id=int(owner.id),
        credential_id=result.credential_id,
        public_key=result.public_key_b64,
        sign_count=result.sign_count,
        aaguid=result.aaguid,
        transports=",".join(result.transports),
        device_type=result.device_type,
        method=method,
        label=f"{method} · {dt.date.today().isoformat()}",
        status="active",
    )
    db.add(credential)
    biometrics.log_verification(
        db,
        school_id=user.school_id,
        owner_type=payload.owner_type,
        owner_id=int(owner.id),
        purpose="enrollment_check",
        result="success",
        credential_id=result.credential_id,
        person_label=_display_name(payload.owner_type, owner),
        detail=f"Enrolled {method} authenticator (attestation {result.device_type})",
        operated_by=user.id,
    )
    db.commit()
    websocket_manager.broadcast_sync(
        "biometric_enrolled",
        {
            "school_id": user.school_id,
            "owner_type": payload.owner_type,
            "owner_id": int(owner.id),
            "method": method,
        },
    )
    return {"credential": _credential_payload(credential)}


# --- verification station ---------------------------------------------------


@router.post("/verify/options")
def verify_options(
    payload: BiometricVerifyOptionsRequest,
    request: Request,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Resolve a person by roll number / staff ID and issue an assertion challenge."""
    context = biometrics.resolve_context(request)
    owner = _resolve_by_identifier(db, user.school_id, payload.owner_type, payload.identifier)
    credentials = biometrics.active_credentials(db, owner_type=payload.owner_type, owner_id=int(owner.id))
    if not credentials:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{_display_name(payload.owner_type, owner)} has no active biometric enrollment — enroll first",
        )
    challenge = secrets.token_bytes(32)
    encoded = biometrics.b64url_encode(challenge)
    _challenge_store.issue(encoded, context.origin)
    options = biometrics.generate_authentication_options(
        context, challenge=challenge, allow_credential_ids=[c.credential_id for c in credentials]
    )
    return {
        "owner": {
            "owner_type": payload.owner_type,
            "owner_id": int(owner.id),
            "name": _display_name(payload.owner_type, owner),
            "identifier": owner.roll_number if payload.owner_type == "student" else owner.email,
        },
        "purpose": payload.purpose,
        "credentials": [_credential_payload(c) for c in credentials],
        **options,
    }


@router.post("/verify/complete")
def verify_complete(
    payload: BiometricVerifyCompleteRequest,
    request: Request,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Verify the assertion, stamp the timestamped log, and broadcast the event."""
    context = biometrics.resolve_context(request)
    if not _challenge_store.contains(payload.expected_challenge):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown or expired verification challenge")
    owner = _resolve_owner(db, user.school_id, payload.owner_type, payload.owner_id)
    credential = db.execute(
        select(BiometricCredential).where(BiometricCredential.credential_id == payload.credential_id)
    ).scalar_one_or_none()

    label = _display_name(payload.owner_type, owner)
    if credential is None or credential.owner_id != int(owner.id) or credential.owner_type != payload.owner_type:
        biometrics.log_verification(
            db, school_id=user.school_id, owner_type=payload.owner_type, owner_id=int(owner.id),
            purpose=payload.purpose, result="unknown_credential", credential_id=payload.credential_id,
            person_label=label, detail="Assertion referenced an unregistered credential", operated_by=user.id,
        )
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown credential")

    if credential.status != "active":
        biometrics.log_verification(
            db, school_id=user.school_id, owner_type=payload.owner_type, owner_id=int(owner.id),
            purpose=payload.purpose, result="revoked_credential", credential_id=credential.credential_id,
            person_label=label, detail="Credential is revoked", operated_by=user.id,
        )
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This credential has been revoked — re-scan required")

    try:
        new_count = biometrics.verify_assertion(
            context,
            credential=credential,
            credential_b64=payload.credential_id,
            client_data_b64=payload.client_data_b64,
            authenticator_data_b64=payload.authenticator_data_b64,
            signature_b64=payload.signature_b64,
            expected_challenge=payload.expected_challenge,
        )
    except ValueError as exc:
        biometrics.log_verification(
            db, school_id=user.school_id, owner_type=payload.owner_type, owner_id=int(owner.id),
            purpose=payload.purpose, result="failed", credential_id=credential.credential_id,
            person_label=label, detail=str(exc), operated_by=user.id,
        )
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Verification failed: {exc}")

    credential.sign_count = int(new_count)
    credential.last_used_at = dt.datetime.now()
    entry = biometrics.log_verification(
        db, school_id=user.school_id, owner_type=payload.owner_type, owner_id=int(owner.id),
        purpose=payload.purpose, result="success", credential_id=credential.credential_id,
        person_label=label,
        detail=f"{payload.purpose} verified via {credential.method} hardware",
        operated_by=user.id,
    )
    db.commit()
    _challenge_store.consume(payload.expected_challenge, payload.credential_id)
    websocket_manager.broadcast_sync(
        "biometric_verified",
        {
            "school_id": user.school_id,
            "owner_type": payload.owner_type,
            "owner_id": int(owner.id),
            "person": label,
            "purpose": payload.purpose,
            "result": "success",
        },
    )
    return {
        "result": "success",
        "person": label,
        "owner_type": payload.owner_type,
        "owner_id": int(owner.id),
        "identifier": owner.roll_number if payload.owner_type == "student" else owner.email,
        "purpose": payload.purpose,
        "method": credential.method,
        "verified_at": entry.verified_at.isoformat() if entry.verified_at else None,
    }


# --- credential lifecycle ---------------------------------------------------


@router.delete("/credentials/{credential_id}")
def revoke_credential(
    credential_id: int,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    credential = db.execute(
        select(BiometricCredential).where(
            BiometricCredential.id == credential_id,
            BiometricCredential.school_id == user.school_id,
        )
    ).scalar_one_or_none()
    if not credential:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credential not found")
    credential.status = "revoked"
    credential.revoked_at = dt.datetime.now()
    db.commit()
    return {"credential": _credential_payload(credential)}


@router.post("/credentials/{credential_id}/rescan")
def rescan_credential(
    credential_id: int,
    request: Request,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    """Hardware re-scan: revoke the credential and open a fresh enrollment."""
    context = biometrics.resolve_context(request)
    credential = db.execute(
        select(BiometricCredential).where(
            BiometricCredential.id == credential_id,
            BiometricCredential.school_id == user.school_id,
        )
    ).scalar_one_or_none()
    if not credential:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credential not found")

    credential.status = "revoked"
    credential.revoked_at = dt.datetime.now()

    owner = _resolve_owner(db, user.school_id, credential.owner_type, int(credential.owner_id))
    owner_name = (
        _display_name("staff", owner)
        if credential.owner_type == "staff"
        else f"{owner.first_name} {owner.last_name} ({owner.roll_number})"
    )
    challenge = secrets.token_bytes(32)
    encoded = biometrics.b64url_encode(challenge)
    _challenge_store.issue(encoded, context.origin)
    options = biometrics.generate_registration_options(
        context,
        owner_type=credential.owner_type,
        owner_id=int(owner.id),
        owner_name=owner_name,
        exclude=[],
    )
    biometrics.log_verification(
        db, school_id=user.school_id, owner_type=credential.owner_type, owner_id=int(owner.id),
        purpose="enrollment_check", result="revoked_credential", credential_id=credential.credential_id,
        person_label=owner_name, detail="Hardware re-scan requested — credential revoked for re-enrollment",
        operated_by=user.id,
    )
    db.commit()
    return {
        "revoked": _credential_payload(credential),
        "re_enroll": {
            "owner": {"owner_type": credential.owner_type, "owner_id": int(owner.id), "name": owner_name},
            **options,
        },
    }


# --- single-use challenge registry ------------------------------------------
# Challenges are held in-process with short TTLs. The registry is keyed by the
# base64 challenge and bound to the origin that issued it; enrollment consumes
# each challenge exactly once, assertions check membership then consume.


class _ChallengeRegistry:
    TTL_SECONDS = 180

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}

    def issue(self, challenge: str, origin: str) -> None:
        self._evict()
        import time

        self._store[challenge] = (origin, time.monotonic())

    def contains(self, challenge: str) -> bool:
        self._evict()
        return challenge in self._store

    def consume(self, challenge: str, credential_id: str) -> bool:
        """Consume an enrollment challenge (single use, per credential binding)."""
        self._evict()
        entry = self._store.pop(challenge, None)
        return entry is not None

    def _evict(self) -> None:
        import time

        now = time.monotonic()
        expired = [key for key, (_, issued) in self._store.items() if now - issued > self.TTL_SECONDS]
        for key in expired:
            self._store.pop(key, None)


_challenge_store = _ChallengeRegistry()

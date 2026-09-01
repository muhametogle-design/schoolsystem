"""Role-gated photo & media management engine (Refinement 5).

Profile photos ride on the existing student/staff profile payloads as data
URLs, which keeps the portable SQLite tier object-store free.

Write model
-----------
* **School Managers / Admins** — full upload, replace and delete rights for
  both student and teacher media, audited on every mutation.
* **Teachers and students** — strictly read-only: the payload carries the
  image but every write route behind this router is manager-gated, so a
  teacher (or a stolen teacher token) cannot overwrite anyone's avatar, and
  the financial firewall still refuses state roles outright.

Payload safety: uploads must be ``data:image/(png|jpeg|webp|gif);base64,…``
URLs and decode to at most 512 KiB, keeping profile list responses small.
"""

from __future__ import annotations

import base64
import binascii
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import _audit, require_school
from app.api.management import teacher_payload
from app.api.students import _profile as student_profile
from app.core.db import get_db
from app.models import Student, User
from app.schemas import PhotoUpdate
from sqlalchemy import or_

router = APIRouter(prefix="/api/v1/school/media", tags=["profile-media"])

# Hard write gate for the whole engine: school managers (tenant admins) only.
manager_only = require_school("school_manager")

_DATA_URL_RE = re.compile(
    r"^data:image/(?P<kind>png|jpe?g|webp|gif);base64,(?P<body>[A-Za-z0-9+/=\r\n]+)$"
)
#: 512 KiB decoded ceiling — generous for a 512×512 avatar, small for a row.
MAX_PHOTO_BYTES = 512 * 1024


def _decode_photo(photo_data: str) -> bytes:
    """Validate a data-URL image payload and return the decoded bytes."""
    match = _DATA_URL_RE.match(photo_data.strip())
    if not match:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Photo must be a data URL with an image/* MIME type (png, jpeg, webp or gif)",
        )
    try:
        blob = base64.b64decode(match.group("body"), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Photo data is not valid base64") from exc
    if not blob:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Photo data is empty")
    if len(blob) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Photo exceeds the {MAX_PHOTO_BYTES // 1024} KiB media limit — crop or compress it first",
        )
    return blob


def _student_or_404(db: Session, school_id: int, key: str) -> Student:
    student = (
        db.query(Student)
        .filter(
            Student.school_id == school_id,
            or_(Student.national_student_id == key, Student.roll_number == key),
        )
        .one_or_none()
    )
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No student with roll number {key}")
    return student


def _teacher_or_404(db: Session, school_id: int, teacher_id: int) -> User:
    teacher = (
        db.query(User)
        .filter(User.school_id == school_id, User.id == teacher_id, User.role == "teacher")
        .one_or_none()
    )
    if not teacher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Teacher not found in this school")
    return teacher


# --------------------------------------------------------------------------- #
# Student media
# --------------------------------------------------------------------------- #
@router.put("/students/{key}/photo")
def upload_student_photo(
    key: str,
    payload: PhotoUpdate,
    request: Request,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """Upload/replace a student's profile photo (manager-only, audited)."""
    _decode_photo(payload.photo_data)
    student = _student_or_404(db, user.school_id, key)
    student.photo_data = payload.photo_data.strip()
    db.commit()
    _audit(db, user, request, "ALLOWED", f"Profile photo updated for student {student.roll_number}")
    return {"message": f"Photo updated for {student.first_name} {student.last_name}.", "student": student_profile(student)}


@router.delete("/students/{key}/photo")
def delete_student_photo(
    key: str,
    request: Request,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    student = _student_or_404(db, user.school_id, key)
    student.photo_data = None
    db.commit()
    _audit(db, user, request, "ALLOWED", f"Profile photo removed for student {student.roll_number}")
    return {"message": "Photo removed.", "student": student_profile(student)}


# --------------------------------------------------------------------------- #
# Teacher media
# --------------------------------------------------------------------------- #
@router.put("/teachers/{teacher_id}/photo")
def upload_teacher_photo(
    teacher_id: int,
    payload: PhotoUpdate,
    request: Request,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """Upload/replace a teacher's profile photo (manager-only, audited)."""
    _decode_photo(payload.photo_data)
    teacher = _teacher_or_404(db, user.school_id, teacher_id)
    teacher.photo_data = payload.photo_data.strip()
    db.commit()
    _audit(db, user, request, "ALLOWED", f"Profile photo updated for staff user #{teacher.id}")
    return {"message": "Staff photo updated.", "teacher": teacher_payload(db, teacher)}


@router.delete("/teachers/{teacher_id}/photo")
def delete_teacher_photo(
    teacher_id: int,
    request: Request,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    teacher = _teacher_or_404(db, user.school_id, teacher_id)
    teacher.photo_data = None
    db.commit()
    _audit(db, user, request, "ALLOWED", f"Profile photo removed for staff user #{teacher.id}")
    return {"message": "Staff photo removed.", "teacher": teacher_payload(db, teacher)}

"""School-admin management APIs: staff, curriculum, class breakdowns, profile.

Every route is scoped through the authenticated tenant. The only private
billing-contact serializer in this module is guarded by ``school_manager``;
State routes never import this module or its financial fields.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_school
from app.core.db import get_db
from app.core.security import hash_password
from app.core.ws import manager as websocket_manager
from app.models import (
    PrivateSchool,
    SchoolClass,
    SchoolUiConfig,
    Student,
    Subject,
    TeachingAssignment,
    User,
)
from app.schemas import (
    ClassUpdate,
    PhotoUploadRequest,
    SchoolProfileUpdate,
    SubjectUpdate,
    TeacherCreate,
    TeacherUpdate,
    TeachingAssignmentUpdate,
    UiConfigPayload,
)
from app.services.school_template import CORE_SUBJECTS, class_sort_key, mandatory_subjects_for_level
from app.services.student_id import generate_unique_staff_identifier

router = APIRouter(prefix="/api/v1/school", tags=["school-management"])

any_school_user = require_school()
manager_only = require_school("school_manager")


def _class_label(klass: SchoolClass | None) -> str | None:
    return f"{klass.class_level} {klass.class_stream}" if klass else None


def _full_name(person: User | None) -> str | None:
    if not person:
        return None
    return f"{person.first_name or ''} {person.last_name or ''}".strip() or person.email


def _teacher_assignments(db: Session, teacher_id: int, school_id: int) -> list[dict]:
    rows = (
        db.query(TeachingAssignment, SchoolClass, Subject)
        .join(SchoolClass, TeachingAssignment.class_id == SchoolClass.id)
        .join(Subject, TeachingAssignment.subject_id == Subject.id)
        .filter(
            TeachingAssignment.school_id == school_id,
            TeachingAssignment.teacher_id == teacher_id,
        )
        .all()
    )
    rows.sort(key=lambda row: (class_sort_key(row[1]), row[2].subject_name.casefold(), row[2].id))
    return [
        {
            "assignment_id": assignment.id,
            "class_id": klass.id,
            "class_level": klass.class_level,
            "class_stream": klass.class_stream,
            "class_label": _class_label(klass),
            "subject_id": subject.id,
            "subject_code": subject.subject_code,
            "subject_name": subject.subject_name,
        }
        for assignment, klass, subject in rows
    ]


def teacher_payload(db: Session, teacher: User, *, include_assignments: bool = True) -> dict:
    """Safe staff serializer shared by tenant and state academic views."""
    assignments = _teacher_assignments(db, teacher.id, teacher.school_id) if include_assignments else []
    homerooms = (
        db.query(SchoolClass)
        .filter_by(school_id=teacher.school_id, class_teacher_id=teacher.id)
        .all()
    )
    homerooms.sort(key=class_sort_key)
    return {
        "id": teacher.id,
        "staff_identifier": teacher.staff_identifier,
        "ne_tid": teacher.staff_identifier,
        "name": _full_name(teacher),
        "first_name": teacher.first_name,
        "last_name": teacher.last_name,
        "email": teacher.email,
        "phone": teacher.phone,
        "qualifications": teacher.qualifications,
        "designation": teacher.designation,
        "bio": teacher.bio,
        "photo_url": teacher.photo_url,
        "is_active": bool(teacher.is_active),
        "assignment_count": len(assignments),
        "assignments": assignments,
        "assigned_subjects": [
            {
                "subject_id": assignment["subject_id"],
                "subject_code": assignment["subject_code"],
                "subject_name": assignment["subject_name"],
                "class_level": assignment["class_level"],
                "class_id": assignment["class_id"],
                "class_label": assignment["class_label"],
            }
            for assignment in assignments
        ],
        "classroom_schedule": [
            {
                "class_id": klass.id,
                "class_level": klass.class_level,
                "class_stream": klass.class_stream,
                "class_label": _class_label(klass),
                "room_number": klass.room_number,
            }
            for klass in homerooms
        ],
    }


def _directory_teacher_payload(db: Session, teacher: User) -> dict:
    """Colleague-visible directory entry: timetable identity ONLY.

    No email, phone, staff credentials, qualifications, bio, payroll or any
    other personal record — teachers cannot inspect each other's files.
    """
    assignments = _teacher_assignments(db, teacher.id, teacher.school_id)
    return {
        "id": teacher.id,
        "name": _full_name(teacher),
        "first_name": teacher.first_name,
        "last_name": teacher.last_name,
        "designation": teacher.designation,
        "photo_url": teacher.photo_url,
        "is_active": bool(teacher.is_active),
        "assignment_count": len(assignments),
        "assignments": assignments,
        "restricted": True,
    }


def _school_or_404(db: Session, school_id: int | None) -> PrivateSchool:
    school = db.get(PrivateSchool, school_id)
    if not school:
        raise HTTPException(404, "School not found")
    return school


def _teacher_or_404(db: Session, school_id: int, teacher_id: int) -> User:
    teacher = db.query(User).filter_by(id=teacher_id, school_id=school_id, role="teacher").one_or_none()
    if not teacher:
        raise HTTPException(404, "Teacher not found in this school")
    return teacher


def _emit_structure_change(school: PrivateSchool, action: str) -> None:
    websocket_manager.broadcast_sync(
        "academic_structure_changed",
        {
            "school_id": school.id,
            "school_name": school.school_name,
            "school_code": school.school_code,
            "action": action,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


def _reassign_teacher_work(db: Session, teacher: User, school_id: int) -> tuple[int, User | None]:
    """Move active curriculum/homeroom work before a teacher exits service."""
    replacement = (
        db.query(User)
        .filter(
            User.school_id == school_id,
            User.role == "teacher",
            User.is_active.is_(True),
            User.id != teacher.id,
        )
        .order_by(User.id)
        .first()
    )
    assigned_count = db.query(TeachingAssignment).filter_by(
        school_id=school_id, teacher_id=teacher.id
    ).count()
    if assigned_count and not replacement:
        raise HTTPException(
            409,
            "Assign another active teacher before deactivating or removing the final teacher with curriculum assignments",
        )
    if replacement:
        db.query(TeachingAssignment).filter_by(
            school_id=school_id, teacher_id=teacher.id
        ).update({TeachingAssignment.teacher_id: replacement.id}, synchronize_session=False)
        db.query(SchoolClass).filter_by(
            school_id=school_id, class_teacher_id=teacher.id
        ).update({SchoolClass.class_teacher_id: replacement.id}, synchronize_session=False)
    return assigned_count, replacement


# --------------------------------------------------------------------------- #
# Tenant identity and private billing-contact profile
# --------------------------------------------------------------------------- #
@router.get("/profile")
def school_profile(user: User = Depends(manager_only), db: Session = Depends(get_db)):
    school = _school_or_404(db, user.school_id)
    return {
        "id": school.id,
        "school_code": school.school_code,
        "school_name": school.school_name,
        "state_license_number": school.state_license_number,
        "proprietor_name": school.proprietor_name,
        "contact_phone": school.contact_phone,
        "contact_email": school.contact_email,
        "physical_address": school.physical_address,
        "accreditation_status": school.accreditation_status,
        "billing": {
            "contact_name": school.billing_contact_name,
            "phone": school.billing_phone,
            "email": school.billing_email,
            "address": school.billing_address,
            "notes": school.billing_notes,
        },
    }


@router.patch("/profile")
def update_school_profile(
    payload: SchoolProfileUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    school = _school_or_404(db, user.school_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "billing_contact_name":
            school.billing_contact_name = value
        elif field == "billing_phone":
            school.billing_phone = value
        elif field == "billing_email":
            school.billing_email = str(value) if value is not None else None
        elif field == "billing_address":
            school.billing_address = value
        elif field == "billing_notes":
            school.billing_notes = value
        elif field == "contact_email":
            school.contact_email = str(value) if value is not None else None
        else:
            setattr(school, field, value)
    db.commit()
    _emit_structure_change(school, "school_profile_updated")
    return {"message": "School and billing profile updated", "school_code": school.school_code}


# --------------------------------------------------------------------------- #
# Teacher CRUD and profiles
# --------------------------------------------------------------------------- #
@router.get("/teachers")
def list_teachers(user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    query = db.query(User).filter_by(school_id=user.school_id, role="teacher")
    # Teaching staff get the active directory; an administrator gets inactive
    # records too so they can restore or remove a profile.
    if user.role != "school_manager":
        query = query.filter(User.is_active.is_(True))
    teachers = query.order_by(User.last_name, User.first_name, User.id).all()
    if user.role == "school_manager":
        return {"teachers": [teacher_payload(db, teacher) for teacher in teachers]}
    # PRIVACY WALL: a teacher sees the public directory (name, designation,
    # timetable) for colleagues and full detail only for their own record.
    # Personal contact data, credentials and biography stay manager-private.
    return {
        "teachers": [
            teacher_payload(db, teacher)
            if teacher.id == user.id
            else _directory_teacher_payload(db, teacher)
            for teacher in teachers
        ]
    }


@router.get("/teachers/{teacher_id}")
def get_teacher(teacher_id: int, user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    teacher = _teacher_or_404(db, user.school_id, teacher_id)
    if user.role != "school_manager" and teacher.id != user.id:
        # A teacher may open only their own full profile.
        return {"teacher": _directory_teacher_payload(db, teacher)}
    return {"teacher": teacher_payload(db, teacher)}


@router.post("/teachers", status_code=status.HTTP_201_CREATED)
def create_teacher(
    payload: TeacherCreate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    email = str(payload.email).lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "A user with this email already exists")
    teacher = User(
        school_id=user.school_id,
        email=email,
        password_hash=hash_password(payload.password),
        role="teacher",
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        staff_identifier=generate_unique_staff_identifier(db, "teacher", str(dt.date.today().year)),
        phone=payload.phone,
        qualifications=payload.qualifications,
        designation=payload.designation or "Teacher",
        bio=payload.bio,
        is_active=payload.is_active,
    )
    db.add(teacher)
    db.commit()
    school = _school_or_404(db, user.school_id)
    _emit_structure_change(school, "teacher_created")
    return {"teacher": teacher_payload(db, teacher)}


@router.patch("/teachers/{teacher_id}")
def update_teacher(
    teacher_id: int,
    payload: TeacherUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    teacher = _teacher_or_404(db, user.school_id, teacher_id)
    values = payload.model_dump(exclude_unset=True)
    if "email" in values:
        email = str(values.pop("email")).lower()
        existing = db.query(User).filter(User.email == email, User.id != teacher.id).first()
        if existing:
            raise HTTPException(409, "A user with this email already exists")
        teacher.email = email
    if "password" in values:
        password = values.pop("password")
        if password:
            teacher.password_hash = hash_password(password)
    if values.get("is_active") is False and teacher.is_active:
        _reassign_teacher_work(db, teacher, user.school_id)
    for field, value in values.items():
        setattr(teacher, field, value)
    db.commit()
    school = _school_or_404(db, user.school_id)
    _emit_structure_change(school, "teacher_updated")
    return {"teacher": teacher_payload(db, teacher)}


@router.delete("/teachers/{teacher_id}")
def delete_teacher(
    teacher_id: int,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    teacher = _teacher_or_404(db, user.school_id, teacher_id)
    # A manager cannot accidentally erase their own account through a crafted
    # teacher URL, even though roles are mutually exclusive in normal UI flow.
    if teacher.id == user.id:
        raise HTTPException(409, "You cannot remove your own account")

    # Preserve the required one-teacher-per-class-subject mapping. A manager
    # can remove staff, but cannot leave the curriculum structurally broken.
    assigned_count, replacement = _reassign_teacher_work(db, teacher, user.school_id)
    db.delete(teacher)
    db.commit()
    school = _school_or_404(db, user.school_id)
    _emit_structure_change(school, "teacher_removed")
    return {
        "deleted": True,
        "teacher_id": teacher_id,
        "assignments_reassigned": assigned_count,
        "replacement_teacher_id": replacement.id if replacement else None,
    }


# --------------------------------------------------------------------------- #
# Class and subject setup
# --------------------------------------------------------------------------- #
@router.patch("/classes/{class_id}")
def update_class(
    class_id: int,
    payload: ClassUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    klass = db.query(SchoolClass).filter_by(id=class_id, school_id=user.school_id).one_or_none()
    if not klass:
        raise HTTPException(404, "Class not found in this school")
    values = payload.model_dump(exclude_unset=True)
    if "class_stream" in values:
        stream = values["class_stream"].strip()
        duplicate = db.query(SchoolClass).filter(
            SchoolClass.school_id == user.school_id,
            SchoolClass.class_level == klass.class_level,
            SchoolClass.class_stream == stream,
            SchoolClass.id != klass.id,
        ).first()
        if duplicate:
            raise HTTPException(409, "This class level + stream already exists")
        klass.class_stream = stream
        values.pop("class_stream")
    if "class_teacher_id" in values and values["class_teacher_id"] is not None:
        _teacher_or_404(db, user.school_id, values["class_teacher_id"])
    for field, value in values.items():
        setattr(klass, field, value)
    db.commit()
    school = _school_or_404(db, user.school_id)
    _emit_structure_change(school, "class_updated")
    return {"id": klass.id, "class_label": _class_label(klass)}


@router.delete("/classes/{class_id}")
def delete_class(class_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    klass = db.query(SchoolClass).filter_by(id=class_id, school_id=user.school_id).one_or_none()
    if not klass:
        raise HTTPException(404, "Class not found in this school")
    if db.query(Student).filter_by(current_class_id=klass.id, is_active=True).count():
        raise HTTPException(409, "Move or deactivate enrolled students before removing this class")
    db.delete(klass)
    db.commit()
    school = _school_or_404(db, user.school_id)
    _emit_structure_change(school, "class_removed")
    return {"deleted": True, "class_id": class_id}


@router.patch("/subjects/{subject_id}")
def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    subject = db.query(Subject).filter_by(id=subject_id, school_id=user.school_id).one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found in this school")
    values = payload.model_dump(exclude_unset=True)
    core_subject_names = {name for _, name in CORE_SUBJECTS}
    if subject.subject_name in core_subject_names and "subject_name" in values:
        if values["subject_name"].strip() != subject.subject_name:
            raise HTTPException(409, "A mandatory core subject name cannot be changed")
    if "subject_code" in values:
        values["subject_code"] = values["subject_code"].strip().upper()
        duplicate = db.query(Subject).filter(
            Subject.school_id == user.school_id,
            Subject.class_level == subject.class_level,
            Subject.subject_code == values["subject_code"],
            Subject.id != subject.id,
        ).first()
        if duplicate:
            raise HTTPException(409, "Subject code already registered for this class level")
    for field, value in values.items():
        setattr(subject, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    school = _school_or_404(db, user.school_id)
    _emit_structure_change(school, "subject_updated")
    return {"id": subject.id, "subject_name": subject.subject_name}


@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    subject = db.query(Subject).filter_by(id=subject_id, school_id=user.school_id).one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found in this school")
    if subject.subject_name in {name for _, name in CORE_SUBJECTS}:
        raise HTTPException(409, "Core curriculum subjects cannot be removed")
    db.delete(subject)
    db.commit()
    school = _school_or_404(db, user.school_id)
    _emit_structure_change(school, "subject_removed")
    return {"deleted": True, "subject_id": subject_id}


@router.put("/classes/{class_id}/subjects/{subject_id}/assignment")
def assign_subject_teacher(
    class_id: int,
    subject_id: int,
    payload: TeachingAssignmentUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    klass = db.query(SchoolClass).filter_by(id=class_id, school_id=user.school_id).one_or_none()
    subject = db.query(Subject).filter_by(id=subject_id, school_id=user.school_id).one_or_none()
    if not klass or not subject:
        raise HTTPException(404, "Class or subject not found in this school")
    if subject.class_level != klass.class_level:
        raise HTTPException(422, "Subject does not belong to this class level")
    teacher = _teacher_or_404(db, user.school_id, payload.teacher_id)
    assignment = db.query(TeachingAssignment).filter_by(
        school_id=user.school_id, class_id=klass.id, subject_id=subject.id
    ).one_or_none()
    if assignment is None:
        assignment = TeachingAssignment(
            school_id=user.school_id,
            class_id=klass.id,
            subject_id=subject.id,
            teacher_id=teacher.id,
        )
        db.add(assignment)
    else:
        assignment.teacher_id = teacher.id
    db.commit()
    school = _school_or_404(db, user.school_id)
    _emit_structure_change(school, "subject_teacher_assigned")
    return {
        "assignment_id": assignment.id,
        "class_id": klass.id,
        "subject_id": subject.id,
        "teacher": {"id": teacher.id, "name": _full_name(teacher)},
    }


# --------------------------------------------------------------------------- #
# Class breakdown (academic only; available to authorized tenant staff)
# --------------------------------------------------------------------------- #
@router.get("/classes/{class_id}/breakdown")
def class_breakdown(class_id: int, user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    klass = (
        db.query(SchoolClass)
        .options(joinedload(SchoolClass.students))
        .filter_by(id=class_id, school_id=user.school_id)
        .one_or_none()
    )
    if not klass:
        raise HTTPException(404, "Class not found in this school")
    subjects = mandatory_subjects_for_level(db, user.school_id, klass.class_level)
    assignments = {
        assignment.subject_id: assignment
        for assignment in db.query(TeachingAssignment)
        .options(joinedload(TeachingAssignment.teacher))
        .filter_by(school_id=user.school_id, class_id=klass.id)
        .all()
    }
    students = sorted(
        (student for student in klass.students if student.is_active),
        key=lambda student: (student.last_name.casefold(), student.first_name.casefold(), student.id),
    )
    return {
        "class": {
            "id": klass.id,
            "class_level": klass.class_level,
            "class_stream": klass.class_stream,
            "class_label": _class_label(klass),
            "room_number": klass.room_number,
            "student_count": len(students),
        },
        "students": [
            {
                "id": student.id,
                "roll_number": student.roll_number,
                "national_student_id": student.national_student_id,
                "name": f"{student.first_name} {student.last_name}",
                "first_name": student.first_name,
                "last_name": student.last_name,
            }
            for student in students
        ],
        "subjects": [
            {
                "id": subject.id,
                "subject_code": subject.subject_code,
                "subject_name": subject.subject_name,
                "class_level": subject.class_level,
                "assignment_id": assignments[subject.id].id if subject.id in assignments else None,
                "teacher": (
                    {
                        "id": assignments[subject.id].teacher.id,
                        "name": _full_name(assignments[subject.id].teacher),
                        "staff_identifier": assignments[subject.id].teacher.staff_identifier,
                    }
                    if subject.id in assignments and assignments[subject.id].teacher
                    else None
                ),
            }
            for subject in subjects
        ],
        "unassigned_subject_count": sum(
            1 for subject in subjects if subject.id not in assignments or not assignments[subject.id].teacher_id
        ),
    }


# --------------------------------------------------------------------------- #
# Role-gated media management — profile photos (managers/admins only)
# --------------------------------------------------------------------------- #
@router.put("/teachers/{teacher_id}/photo")
def set_teacher_photo(
    teacher_id: int,
    payload: PhotoUploadRequest,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """Upload/replace (or clear with ``photo: null``) a staff profile photo."""
    teacher = _teacher_or_404(db, user.school_id, teacher_id)
    teacher.photo_url = payload.photo
    db.commit()
    return {"id": teacher.id, "photo_url": teacher.photo_url, "updated": True}


# --------------------------------------------------------------------------- #
# Design & layout configuration — draft lives client-side, this is 'Push Live'
# --------------------------------------------------------------------------- #
import json as _json  # noqa: E402  (scoped utility import)

DEFAULT_UI_CONFIG = {
    "accent": "#2563eb",
    "font": "sans",
    "blocks": {
        "profileCard": True,
        "academicOverview": True,
        "attendanceSummary": True,
        "biometricsBadge": True,
    },
}


@router.get("/ui-config")
def get_ui_config(user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    """Published design system for this tenant (every role reads it)."""
    row = db.get(SchoolUiConfig, user.school_id)
    config = dict(DEFAULT_UI_CONFIG)
    if row:
        try:
            stored = _json.loads(row.config or "{}")
        except ValueError:
            stored = {}
        config.update({k: v for k, v in stored.items() if k in DEFAULT_UI_CONFIG})
        merged_blocks = dict(DEFAULT_UI_CONFIG["blocks"])
        merged_blocks.update(stored.get("blocks") or {})
        config["blocks"] = merged_blocks
    return {
        "config": config,
        "published_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "can_publish": user.role == "school_manager",
    }


@router.put("/ui-config")
def publish_ui_config(
    payload: UiConfigPayload,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """'Push Live' — sync theme variables and block layout to production."""
    config = {
        "accent": payload.accent or DEFAULT_UI_CONFIG["accent"],
        "font": payload.font or DEFAULT_UI_CONFIG["font"],
        "blocks": {**DEFAULT_UI_CONFIG["blocks"], **payload.blocks},
    }
    row = db.get(SchoolUiConfig, user.school_id)
    if row:
        row.config = _json.dumps(config)
        row.published_by = user.id
    else:
        db.add(
            SchoolUiConfig(
                school_id=user.school_id, config=_json.dumps(config), published_by=user.id
            )
        )
    db.commit()
    websocket_manager.broadcast_sync("ui_config_published", {"school_id": user.school_id})
    return {"config": config, "published": True}

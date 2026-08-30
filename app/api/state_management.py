"""State Admin tenant provisioning and cross-school academic breakdown APIs.

The State Admin can create/configure tenants and control roll sequences. Both
State Admins and Inspectors can read the class/subject/teacher structure. This
module intentionally imports no financial model and never emits billing data.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, load_only

from app.api.deps import require_state, require_state_admin
from app.core.db import get_db
from app.core.security import hash_password
from app.core.ws import manager as websocket_manager
from app.models import PrivateSchool, SchoolClass, SchoolRollSequence, Student, Subject, TeachingAssignment, User
from app.schemas import RollSequenceUpdate, SchoolCreate, StateSchoolUpdate
from app.services.school_template import (
    allocate_school_code,
    assign_complete_curriculum,
    class_sort_key,
    create_template_teachers,
    mandatory_subjects_for_level,
    provision_school_template,
)
from app.services.student_id import generate_unique_staff_identifier, set_school_roll_sequence

router = APIRouter(prefix="/api/v1/state", tags=["state-administration"])

# State Admin manages public school identity but does not load or serialize a
# tenant's billing contact fields.
STATE_SCHOOL_FIELDS = (
    PrivateSchool.id,
    PrivateSchool.state_license_number,
    PrivateSchool.school_code,
    PrivateSchool.school_name,
    PrivateSchool.proprietor_name,
    PrivateSchool.contact_phone,
    PrivateSchool.contact_email,
    PrivateSchool.physical_address,
    PrivateSchool.accreditation_status,
    PrivateSchool.created_at,
)
STATE_USER_FIELDS = (
    User.id,
    User.school_id,
    User.email,
    User.role,
    User.first_name,
    User.last_name,
    User.staff_identifier,
    User.phone,
    User.qualifications,
    User.designation,
    User.bio,
    User.is_active,
    User.created_at,
)


def _full_name(person: User | None) -> str | None:
    if not person:
        return None
    return f"{person.first_name or ''} {person.last_name or ''}".strip() or person.email


def _class_label(klass: SchoolClass) -> str:
    return f"{klass.class_level} {klass.class_stream}"


def _school_or_404(db: Session, school_id: int) -> PrivateSchool:
    school = (
        db.execute(
            select(PrivateSchool)
            .options(load_only(*STATE_SCHOOL_FIELDS, raiseload=True))
            .where(PrivateSchool.id == school_id)
        )
        .scalar_one_or_none()
    )
    if not school:
        raise HTTPException(404, "Institution not found")
    return school


def _broadcast(school: PrivateSchool, action: str) -> None:
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


@router.get("/school-code-suggestion")
def school_code_suggestion(
    school_name: str = Query(min_length=2, max_length=255),
    _user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    return {"school_code": allocate_school_code(db, school_name), "school_name": school_name}


@router.post("/schools", status_code=status.HTTP_201_CREATED)
def create_school_tenant(
    payload: SchoolCreate,
    user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    """Create a fully provisioned Class 1–12 school tenant.

    The State Admin provides a manager identity. Eight editable faculty
    profiles and 120 subject assignments are created so the template is
    structurally complete from the first sign-in.
    """
    if db.query(PrivateSchool.id).filter_by(state_license_number=payload.state_license_number.strip()).first():
        raise HTTPException(409, "This state licence number is already registered")
    manager_email = str(payload.manager_email).lower()
    if db.query(User.id).filter(User.email == manager_email).first():
        raise HTTPException(409, "A user with the manager email already exists")
    try:
        code = allocate_school_code(db, payload.school_name, payload.school_code)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    school = PrivateSchool(
        state_license_number=payload.state_license_number.strip(),
        school_code=code,
        school_name=payload.school_name.strip(),
        proprietor_name=payload.proprietor_name,
        contact_phone=payload.contact_phone,
        contact_email=str(payload.contact_email) if payload.contact_email else None,
        physical_address=payload.physical_address,
        accreditation_status=payload.accreditation_status,
    )
    db.add(school)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "The school licence number or two-letter code is already in use") from exc
    manager = User(
        school_id=school.id,
        email=manager_email,
        password_hash=hash_password(payload.manager_password),
        role="school_manager",
        first_name=payload.manager_first_name.strip(),
        last_name=payload.manager_last_name.strip(),
        staff_identifier=generate_unique_staff_identifier(db, "school_manager", str(dt.date.today().year)),
        designation="School Administrator",
        is_active=True,
    )
    db.add(manager)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A user with the manager email already exists") from exc

    template = provision_school_template(db, school, streams=payload.streams)
    # Billing rates are initialized for the tenant, but State responses never
    # expose even private finance configuration metadata.
    template.pop("tuition_rates_created", None)
    teachers = create_template_teachers(db, school, count=8)
    assignment_count = assign_complete_curriculum(db, school, teachers, overwrite=True)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Could not provision a unique school tenant template") from exc
    _broadcast(school, "school_provisioned")
    return {
        "id": school.id,
        "school_name": school.school_name,
        "school_code": school.school_code,
        "state_license_number": school.state_license_number,
        "manager": {"id": manager.id, "email": manager.email, "name": _full_name(manager)},
        "template": {
            **template,
            "teachers_created": len(teachers),
            "teacher_assignments_created": assignment_count,
            "roll_sequence_next_value": 10000,
        },
    }


@router.patch("/schools/{school_id}")
def update_school_tenant(
    school_id: int,
    payload: StateSchoolUpdate,
    _user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    """State Admin public tenant configuration; never accepts billing fields."""
    school = _school_or_404(db, school_id)
    values = payload.model_dump(exclude_unset=True)
    if "school_code" in values:
        requested = values.pop("school_code")
        if requested:
            existing_students = db.query(Student).filter_by(school_id=school.id).count()
            if existing_students:
                raise HTTPException(
                    409,
                    "School code cannot change after roll numbers have been issued",
                )
            try:
                school.school_code = allocate_school_code(db, school.school_name, requested)
            except ValueError as exc:
                raise HTTPException(422, str(exc))
    if "state_license_number" in values:
        licence = values["state_license_number"].strip()
        duplicate = db.query(PrivateSchool.id).filter(
            PrivateSchool.state_license_number == licence, PrivateSchool.id != school.id
        ).first()
        if duplicate:
            raise HTTPException(409, "This state licence number is already registered")
        values["state_license_number"] = licence
    for field, value in values.items():
        if field == "contact_email":
            value = str(value) if value else None
        setattr(school, field, value)
    db.commit()
    _broadcast(school, "school_updated")
    return {
        "id": school.id,
        "school_name": school.school_name,
        "school_code": school.school_code,
        "state_license_number": school.state_license_number,
        "accreditation_status": school.accreditation_status,
    }


@router.get("/schools/{school_id}/roll-sequence")
def get_roll_sequence(
    school_id: int,
    _user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    school = _school_or_404(db, school_id)
    sequence = db.get(SchoolRollSequence, school.id)
    return {
        "school_id": school.id,
        "school_code": school.school_code,
        "next_value": sequence.next_value if sequence else 10000,
        "next_roll_number": f"{school.school_code}-{sequence.next_value if sequence else 10000}",
    }


@router.patch("/schools/{school_id}/roll-sequence")
def update_roll_sequence(
    school_id: int,
    payload: RollSequenceUpdate,
    _user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    school = _school_or_404(db, school_id)
    try:
        sequence = set_school_roll_sequence(db, school, payload.next_value)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    db.commit()
    _broadcast(school, "roll_sequence_updated")
    return {
        "school_id": school.id,
        "school_code": school.school_code,
        "next_value": sequence.next_value,
        "next_roll_number": f"{school.school_code}-{sequence.next_value}",
    }


# --------------------------------------------------------------------------- #
# Read-only, cross-school Class 1–12 academic breakdown for Admin + Inspector
# --------------------------------------------------------------------------- #
@router.get("/institutions/{school_id}/classes")
def state_school_classes(
    school_id: int,
    _user: User = Depends(require_state),
    db: Session = Depends(get_db),
):
    _school_or_404(db, school_id)
    classes = (
        db.query(SchoolClass)
        .options(
            joinedload(SchoolClass.students).load_only(
                Student.id, Student.roll_number, Student.first_name, Student.last_name,
                Student.is_active, raiseload=True
            )
        )
        .filter_by(school_id=school_id)
        .all()
    )
    classes.sort(key=class_sort_key)
    return {
        "classes": [
            {
                "id": klass.id,
                "class_level": klass.class_level,
                "class_stream": klass.class_stream,
                "class_label": _class_label(klass),
                "room_number": klass.room_number,
                "student_count": sum(1 for student in klass.students if student.is_active),
            }
            for klass in classes
        ]
    }


@router.get("/institutions/{school_id}/classes/{class_id}/breakdown")
def state_class_breakdown(
    school_id: int,
    class_id: int,
    _user: User = Depends(require_state),
    db: Session = Depends(get_db),
):
    school = _school_or_404(db, school_id)
    klass = (
        db.query(SchoolClass)
        .options(
            joinedload(SchoolClass.students).load_only(
                Student.id, Student.roll_number, Student.first_name, Student.last_name,
                Student.is_active, raiseload=True
            )
        )
        .filter_by(id=class_id, school_id=school.id)
        .one_or_none()
    )
    if not klass:
        raise HTTPException(404, "Class not found in this institution")
    assignments = {
        assignment.subject_id: assignment
        for assignment in db.query(TeachingAssignment)
        .options(
            joinedload(TeachingAssignment.teacher).load_only(*STATE_USER_FIELDS, raiseload=True)
        )
        .filter_by(school_id=school.id, class_id=klass.id)
        .all()
    }
    subjects = mandatory_subjects_for_level(db, school.id, klass.class_level)
    students = sorted(
        (student for student in klass.students if student.is_active),
        key=lambda student: (student.last_name.casefold(), student.first_name.casefold(), student.id),
    )
    return {
        "school": {"id": school.id, "school_name": school.school_name, "school_code": school.school_code},
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
                "name": f"{student.first_name} {student.last_name}",
            }
            for student in students
        ],
        "subjects": [
            {
                "id": subject.id,
                "subject_code": subject.subject_code,
                "subject_name": subject.subject_name,
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

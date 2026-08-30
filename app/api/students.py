"""NE-EMIS student profiles — details page, editing & printable report cards.

Mounted under the tenant ERP prefix. Every query is hard-scoped to
`user.school_id`, so a tenant can never read or mutate another tenant's rows.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.api.deps import require_school
from app.core.db import get_db
from app.models import (
    FEE_STATUSES,
    AcademicYear,
    LiveAttendance,
    PrivateSchool,
    SchoolClass,
    Student,
    StudentGrade,
    Subject,
    User,
)
from app.schemas import StudentCreate, StudentUpdate
from app.services.student_id import generate_school_roll_number

router = APIRouter(prefix="/api/v1/school", tags=["students"])

any_school_user = require_school()
erp_write = require_school("school_manager", "teacher")
manager_only = require_school("school_manager")


def _age(date_of_birth: dt.date | None) -> int | None:
    """Completed years, or None when no date of birth is on file."""
    if not date_of_birth:
        return None
    today = dt.date.today()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


def _class_label(klass: SchoolClass | None) -> str | None:
    return f"{klass.class_level} {klass.class_stream}" if klass else None


def _profile(student: Student) -> dict:
    """Full student profile contract shared by the list, details and lookup."""
    klass = student.current_class
    return {
        "id": student.id,
        # ne_sid remains the stable URL/API key for older clients. New rows use
        # the same value as the school roll number.
        "ne_sid": student.national_student_id,
        "national_student_id": student.national_student_id,
        "roll_number": student.roll_number,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "full_legal_name": f"{student.first_name} {student.last_name}",
        "age": _age(student.date_of_birth),
        "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
        "gender": student.gender,
        "current_class_id": student.current_class_id,
        "class_label": _class_label(klass),
        "class_level": klass.class_level if klass else None,
        "physical_address": student.physical_address,
        "fee_status": student.fee_status,
        "enrollment_date": student.enrollment_date.isoformat() if student.enrollment_date else None,
        "is_active": student.is_active,
        "guardian": {
            "name": student.guardian_name,
            "relationship": student.guardian_relationship,
            "phone": student.guardian_phone,
            "email": student.guardian_email,
            "emergency_phone": student.emergency_contact_phone,
        },
    }


def _scoped_student(ne_sid: str, user: User, db: Session) -> Student:
    """Resolve a student by NE-SID within the caller's tenant, else 404."""
    student = (
        db.query(Student)
        .options(joinedload(Student.current_class))
        .filter(
            Student.school_id == user.school_id,
            or_(Student.national_student_id == ne_sid, Student.roll_number == ne_sid),
        )
        .one_or_none()
    )
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No student with roll number {ne_sid}")
    return student


# --------------------------------------------------------------------------- #
# Class 1 -> 12 accordion grouping
# --------------------------------------------------------------------------- #
@router.get("/students/by-class")
def students_by_class(
    q: str | None = None,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Students grouped by class level for the Class 1-12 accordion.

    Classes are returned in Class 1 -> Class 12 order with `is_empty` so the
    UI can render empty tracks without expanding them.
    """
    query = (
        db.query(Student)
        .options(joinedload(Student.current_class))
        .filter_by(school_id=user.school_id, is_active=True)
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            Student.last_name.ilike(like)
            | Student.first_name.ilike(like)
            | Student.national_student_id.ilike(like)
            | Student.roll_number.ilike(like)
        )

    grouped: dict[str, list[dict]] = defaultdict(list)
    unassigned: list[dict] = []
    for student in query.order_by(Student.last_name, Student.first_name).all():
        payload = _profile(student)
        level = student.current_class.class_level if student.current_class else None
        if level:
            grouped[level].append(payload)
        else:
            unassigned.append(payload)

    def level_key(level: str) -> int:
        return int(level.split()[-1])

    classes = [
        {
            "class_level": level,
            "student_count": len(grouped[level]),
            "students": sorted(grouped[level], key=lambda s: (s["last_name"], s["first_name"])),
        }
        for level in sorted(grouped, key=level_key)
    ]
    return {
        "classes": classes,
        "unassigned": unassigned,
        "total_students": sum(c["student_count"] for c in classes) + len(unassigned),
    }


# --------------------------------------------------------------------------- #
# Student details / create / update
# --------------------------------------------------------------------------- #
@router.get("/students/{ne_sid}")
def student_details(
    ne_sid: str,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Full student profile for the Student Details page."""
    student = _scoped_student(ne_sid, user, db)
    payload = _profile(student)

    # Attendance summary across the whole academic year.
    totals = (
        db.query(
            func.count(LiveAttendance.id),
            func.sum(case((LiveAttendance.status == "Present", 1), else_=0)),
        )
        .filter_by(school_id=user.school_id, student_id=student.id)
        .one()
    )
    recorded = int(totals[0] or 0)
    present = int(totals[1] or 0)
    payload["attendance"] = {
        "days_recorded": recorded,
        "days_present": present,
        "attendance_pct": round(present / recorded * 100, 1) if recorded else None,
    }
    return payload


@router.patch("/students/{ne_sid}")
def update_student(
    ne_sid: str,
    payload: StudentUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """Editable fields on the Student Details page."""
    student = _scoped_student(ne_sid, user, db)

    if payload.current_class_id is not None:
        klass = (
            db.query(SchoolClass)
            .filter_by(id=payload.current_class_id, school_id=user.school_id)
            .one_or_none()
        )
        if not klass:
            raise HTTPException(404, "Class not found in this school")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return {"message": "Student record updated", "student": _profile(student)}


@router.post("/students", status_code=201)
def create_student(
    payload: StudentCreate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """School Manager registration with an automatic immutable roll number."""
    klass = (
        db.query(SchoolClass)
        .filter_by(id=payload.current_class_id, school_id=user.school_id)
        .one_or_none()
    )
    if not klass:
        raise HTTPException(404, "Class not found in this school")

    school = db.get(PrivateSchool, user.school_id)
    if not school:
        raise HTTPException(404, "School not found")
    # Roll numbers are tenant-scoped, sequential and never re-used. Store the
    # value in the legacy national-id field as well so existing deep links and
    # API consumers continue to resolve the same student identifier.
    roll_number = generate_school_roll_number(db, school)
    student = Student(
        school_id=user.school_id,
        national_student_id=roll_number,
        roll_number=roll_number,
        current_class_id=klass.id,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        guardian_name=payload.guardian_name,
        guardian_relationship=payload.guardian_relationship,
        guardian_phone=payload.guardian_phone,
        guardian_email=payload.guardian_email,
        emergency_contact_phone=payload.emergency_contact_phone,
        physical_address=payload.physical_address,
        fee_status=payload.fee_status,
        enrollment_date=dt.date.today(),
        is_active=True,
    )
    db.add(student)
    db.commit()
    return {
        "id": student.id,
        "national_student_id": student.national_student_id,
        "ne_sid": student.national_student_id,
        "roll_number": student.roll_number,
        "class_label": _class_label(klass),
        "message": f"Student registered with roll number {student.roll_number}",
    }


# --------------------------------------------------------------------------- #
# Printable parent assessment report card
# --------------------------------------------------------------------------- #
@router.get("/students/{ne_sid}/report-card")
def report_card(
    ne_sid: str,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Print-ready assessment card: marks, GPA summary and season attendance."""
    student = _scoped_student(ne_sid, user, db)
    school = db.get(PrivateSchool, user.school_id)
    year = db.execute(select(AcademicYear).where(AcademicYear.is_current.is_(True))).scalar_one_or_none()

    # Explicit join (not joinedload) so the ORDER BY can reference subjects:
    # joinedload aliases the table, which puts `subjects.subject_name` outside
    # the FROM clause and makes SQLite reject the statement.
    grades = (
        db.query(StudentGrade)
        .join(Subject, StudentGrade.subject_id == Subject.id)
        .options(contains_eager(StudentGrade.subject))
        .filter(StudentGrade.school_id == user.school_id, StudentGrade.student_id == student.id)
        .order_by(StudentGrade.exam_name, Subject.subject_name)
        .all()
    )

    by_exam: dict[str, list[dict]] = defaultdict(list)
    for grade in grades:
        by_exam[grade.exam_name].append(
            {
                "subject_code": grade.subject.subject_code if grade.subject else None,
                "subject_name": grade.subject.subject_name if grade.subject else None,
                "score": float(grade.numeric_score),
                "grade": _letter_grade(float(grade.numeric_score)),
                "points": _grade_points(float(grade.numeric_score)),
                "is_published": grade.is_published,
            }
        )

    exams = []
    for exam_name, rows in by_exam.items():
        scores = [r["score"] for r in rows]
        points = [r["points"] for r in rows]
        exams.append(
            {
                "exam_name": exam_name,
                "subjects": rows,
                "average_score": round(sum(scores) / len(scores), 1) if scores else None,
                "gpa": round(sum(points) / len(points), 2) if points else None,
                "is_published": all(r["is_published"] for r in rows),
            }
        )

    totals = (
        db.query(
            func.count(LiveAttendance.id),
            func.sum(case((LiveAttendance.status == "Present", 1), else_=0)),
            func.sum(case((LiveAttendance.status == "Absent", 1), else_=0)),
        )
        .filter_by(school_id=user.school_id, student_id=student.id)
        .one()
    )
    recorded = int(totals[0] or 0)
    present = int(totals[1] or 0)
    absent = int(totals[2] or 0)

    class_teacher = None
    if student.current_class and student.current_class.class_teacher_id:
        teacher = db.get(User, student.current_class.class_teacher_id)
        if teacher:
            class_teacher = {
                "name": f"{teacher.first_name} {teacher.last_name}".strip(),
                "staff_identifier": teacher.staff_identifier,
                "designation": teacher.designation,
                "phone": teacher.phone,
            }

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "school": {
            "school_name": school.school_name if school else None,
            "state_license_number": school.state_license_number if school else None,
            "school_code": school.school_code if school else None,
            "physical_address": school.physical_address if school else None,
            "contact_phone": school.contact_phone if school else None,
            "contact_email": school.contact_email if school else None,
            "proprietor_name": school.proprietor_name if school else None,
        },
        "academic_year": {"id": year.id, "label": year.label} if year else None,
        "student": _profile(student),
        "exams": exams,
        "overall": {
            "average_score": (
                round(sum(e["average_score"] for e in exams if e["average_score"] is not None)
                      / len([e for e in exams if e["average_score"] is not None]), 1)
                if any(e["average_score"] is not None for e in exams)
                else None
            ),
            "gpa": (
                round(sum(e["gpa"] for e in exams if e["gpa"] is not None)
                      / len([e for e in exams if e["gpa"] is not None]), 2)
                if any(e["gpa"] is not None for e in exams)
                else None
            ),
        },
        "attendance": {
            "days_recorded": recorded,
            "days_present": present,
            "days_absent": absent,
            "attendance_pct": round(present / recorded * 100, 1) if recorded else None,
        },
        "class_teacher": class_teacher,
        # Rendered as empty boxes on the printed card for the class teacher.
        "sign_off": {"teacher_remarks": "", "teacher_signature": "", "date": ""},
    }


def _letter_grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _grade_points(score: float) -> float:
    return {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}[_letter_grade(score)]

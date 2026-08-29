"""NE-EMIS state oversight — global NE-SID lookup & institutional directory.

Every route here is guarded by `require_state`. In line with the critical
financial firewall, NOTHING in this module exposes tuition, invoices,
payments or balances — only academic records and staff contact details.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.api.deps import require_state
from app.core.db import get_db
from app.models import (
    CLASS_LEVELS,
    LiveAttendance,
    PrivateSchool,
    SchoolClass,
    Student,
    StudentGrade,
    Subject,
    User,
)
from app.services.analytics import state_live_attendance_feed

router = APIRouter(prefix="/api/v1/state", tags=["state-oversight"])


def _age(date_of_birth: dt.date | None) -> int | None:
    if not date_of_birth:
        return None
    today = dt.date.today()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


def _full_name(user: User | None) -> str | None:
    return f"{user.first_name} {user.last_name}".strip() if user else None


# --------------------------------------------------------------------------- #
# Global NE-SID lookup
# --------------------------------------------------------------------------- #
@router.get("/students/lookup")
def global_student_lookup(
    ne_sid: str = Query(min_length=1, description="NE-SID-2026-XY123"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_state),
):
    """Seasonal summary for one student: profile, published marks, attendance.

    Only PUBLISHED marks are returned — the Exam Data Release Valve means
    draft results remain invisible to every state role.
    """
    student = (
        db.query(Student)
        .options(joinedload(Student.current_class), joinedload(Student.school))
        .filter(Student.national_student_id == ne_sid.strip())
        .one_or_none()
    )
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No student found with NE-SID {ne_sid}")

    school: PrivateSchool | None = student.school
    klass: SchoolClass | None = student.current_class

    # Explicit join (not joinedload) so the ORDER BY can reference subjects —
    # joinedload aliases the table out of the FROM clause.
    marks = (
        db.query(StudentGrade)
        .join(Subject, StudentGrade.subject_id == Subject.id)
        .options(contains_eager(StudentGrade.subject))
        .filter(StudentGrade.student_id == student.id, StudentGrade.is_published.is_(True))
        .order_by(StudentGrade.exam_name, Subject.subject_name)
        .all()
    )

    by_exam: dict[str, list[dict]] = defaultdict(list)
    for grade in marks:
        by_exam[grade.exam_name].append(
            {
                "subject_code": grade.subject.subject_code if grade.subject else None,
                "subject_name": grade.subject.subject_name if grade.subject else None,
                "score": float(grade.numeric_score),
                "letter": _letter(float(grade.numeric_score)),
            }
        )

    exams = []
    for exam_name, rows in sorted(by_exam.items()):
        scores = [r["score"] for r in rows]
        exams.append(
            {
                "exam_name": exam_name,
                "subjects": rows,
                "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            }
        )

    attendance_rows = (
        db.query(LiveAttendance)
        .filter_by(student_id=student.id)
        .order_by(LiveAttendance.date.desc())
        .limit(400)
        .all()
    )
    recorded = len(attendance_rows)
    present = sum(1 for a in attendance_rows if a.status == "Present")
    absent = sum(1 for a in attendance_rows if a.status == "Absent")
    late = sum(1 for a in attendance_rows if a.status == "Late")

    # Consecutive absences are flagged as a truancy marker.
    consecutive = 0
    max_consecutive = 0
    for row in sorted(attendance_rows, key=lambda a: a.date):
        consecutive = consecutive + 1 if row.status == "Absent" else 0
        max_consecutive = max(max_consecutive, consecutive)

    return {
        "ne_sid": student.national_student_id,
        "full_legal_name": f"{student.first_name} {student.last_name}",
        "first_name": student.first_name,
        "last_name": student.last_name,
        "age": _age(student.date_of_birth),
        "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
        "gender": student.gender,
        "physical_address": student.physical_address,
        "class_label": f"{klass.class_level} {klass.class_stream}" if klass else None,
        "class_level": klass.class_level if klass else None,
        "school": {
            "id": school.id if school else None,
            "school_name": school.school_name if school else None,
            "state_license_number": school.state_license_number if school else None,
            "physical_address": school.physical_address if school else None,
        },
        "guardian": {
            "name": student.guardian_name,
            "relationship": student.guardian_relationship,
            "phone": student.guardian_phone,
            "email": student.guardian_email,
            "emergency_phone": student.emergency_contact_phone,
        },
        "exams": exams,
        "attendance": {
            "days_recorded": recorded,
            "days_present": present,
            "days_absent": absent,
            "days_late": late,
            "attendance_pct": round(present / recorded * 100, 1) if recorded else None,
            "longest_absence_run": max_consecutive,
            "truancy_flag": max_consecutive >= 3,
        },
        "attendance_log": [
            {"date": a.date.isoformat(), "status": a.status} for a in attendance_rows[:120]
        ],
        # Explicit: the financial tier is never reachable from a state route.
        "financial_data": "RESTRICTED — state roles cannot access financial records",
    }


def _letter(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


# --------------------------------------------------------------------------- #
# Institutional sidebar directory
# --------------------------------------------------------------------------- #
@router.get("/institutions")
def institutions_directory(
    db: Session = Depends(get_db),
    _user: User = Depends(require_state),
):
    """Sidebar directory: every registered school with headline counts."""
    schools = db.execute(select(PrivateSchool).order_by(PrivateSchool.school_name)).scalars().all()

    student_counts = dict(
        db.query(Student.school_id, func.count(Student.id))
        .filter_by(is_active=True)
        .group_by(Student.school_id)
        .all()
    )
    teacher_counts = dict(
        db.query(User.school_id, func.count(User.id))
        .filter(User.role == "teacher", User.is_active.is_(True))
        .group_by(User.school_id)
        .all()
    )

    return {
        "institutions": [
            {
                "id": s.id,
                "school_name": s.school_name,
                "state_license_number": s.state_license_number,
                "accreditation_status": s.accreditation_status,
                "physical_address": s.physical_address,
                "contact_phone": s.contact_phone,
                "contact_email": s.contact_email,
                "student_count": student_counts.get(s.id, 0),
                "teacher_count": teacher_counts.get(s.id, 0),
            }
            for s in schools
        ]
    }


@router.get("/institutions/{school_id}")
def institutional_overview(
    school_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_state),
):
    """Institutional card: principal profile, teacher count and roster."""
    school = db.get(PrivateSchool, school_id)
    if not school:
        raise HTTPException(404, "Institution not found")

    principal = (
        db.query(User)
        .filter_by(school_id=school_id, role="school_manager", is_active=True)
        .first()
    )
    teachers = (
        db.query(User)
        .filter_by(school_id=school_id, role="teacher", is_active=True)
        .order_by(User.last_name, User.first_name)
        .all()
    )

    student_count = (
        db.query(func.count(Student.id)).filter_by(school_id=school_id, is_active=True).scalar()
    )
    class_count = db.query(func.count(SchoolClass.id)).filter_by(school_id=school_id).scalar()

    return {
        "id": school.id,
        "school_name": school.school_name,
        "state_license_number": school.state_license_number,
        "accreditation_status": school.accreditation_status,
        "physical_address": school.physical_address,
        "contact_phone": school.contact_phone,
        "contact_email": school.contact_email,
        "proprietor_name": school.proprietor_name,
        "principal": (
            {
                "ne_mid": principal.staff_identifier,
                "name": _full_name(principal),
                "email": principal.email,
                "phone": principal.phone,
                "designation": principal.designation,
                "qualifications": principal.qualifications,
            }
            if principal
            else None
        ),
        "total_teachers": len(teachers),
        "total_students": student_count,
        "total_classes": class_count,
        "teacher_roster": [
            {
                "id": t.id,
                "ne_tid": t.staff_identifier,
                "name": _full_name(t),
                "phone": t.phone,
                "email": t.email,
                "designation": t.designation,
            }
            for t in teachers
        ],
    }


@router.get("/teachers/{teacher_id}")
def teacher_detail(
    teacher_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_state),
):
    """Teacher card: contact, assigned subjects, qualifications and schedule."""
    teacher = db.get(User, teacher_id)
    if not teacher or teacher.role != "teacher":
        raise HTTPException(404, "Teacher not found")

    school = db.get(PrivateSchool, teacher.school_id) if teacher.school_id else None

    # Subjects this teacher has entered marks for.
    subject_rows = (
        db.query(Subject.subject_code, Subject.subject_name, Subject.class_level)
        .join(StudentGrade, StudentGrade.subject_id == Subject.id)
        .filter(StudentGrade.recorded_by == teacher.id)
        .distinct()
        .order_by(Subject.class_level, Subject.subject_name)
        .all()
    )

    # Homeroom / classroom schedule.
    schedule = (
        db.query(SchoolClass)
        .filter_by(school_id=teacher.school_id, class_teacher_id=teacher.id)
        .order_by(SchoolClass.class_level, SchoolClass.class_stream)
        .all()
    )

    return {
        "id": teacher.id,
        "ne_tid": teacher.staff_identifier,
        "name": _full_name(teacher),
        "email": teacher.email,
        "phone": teacher.phone,
        "qualifications": teacher.qualifications,
        "designation": teacher.designation,
        "school": {
            "id": school.id if school else None,
            "school_name": school.school_name if school else None,
        },
        "assigned_subjects": [
            {"subject_code": code, "subject_name": name, "class_level": level}
            for code, name, level in subject_rows
        ],
        "classroom_schedule": [
            {
                "class_id": c.id,
                "class_level": c.class_level,
                "class_stream": c.class_stream,
                "room_number": c.room_number,
            }
            for c in schedule
        ],
    }


@router.get("/class-levels")
def class_levels(_user: User = Depends(require_state)):
    """Class 1-12 options for the Live Attendance filter dropdown."""
    return {"class_levels": list(CLASS_LEVELS)}

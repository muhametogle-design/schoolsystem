"""NE-EMIS state oversight — global NE-SID lookup & institutional directory.

Every route here is guarded by `require_state`. In line with the critical
financial firewall, NOTHING in this module exposes tuition, invoices,
payments or balances — only academic records and staff contact details.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload, load_only

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
    TeachingAssignment,
    User,
)
from app.services.analytics import state_live_attendance_feed
from app.services.school_template import class_sort_key

router = APIRouter(prefix="/api/v1/state", tags=["state-oversight"])

# State serializers must not accidentally lazy-load tenant billing contact
# columns from PrivateSchool or the finance-adjacent student fee_status field.
# raiseload=True turns any future mistaken attribute access into a server-side
# programming error rather than a silent disclosure.
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
STATE_STUDENT_FIELDS = (
    Student.id,
    Student.school_id,
    Student.national_student_id,
    Student.roll_number,
    Student.current_class_id,
    Student.first_name,
    Student.last_name,
    Student.date_of_birth,
    Student.gender,
    Student.guardian_name,
    Student.guardian_relationship,
    Student.guardian_phone,
    Student.guardian_email,
    Student.emergency_contact_phone,
    Student.physical_address,
    Student.enrollment_date,
    Student.is_active,
    Student.created_at,
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
        .options(
            load_only(*STATE_STUDENT_FIELDS, raiseload=True),
            joinedload(Student.current_class).load_only(
                SchoolClass.id, SchoolClass.class_level, SchoolClass.class_stream, raiseload=True
            ),
            joinedload(Student.school).load_only(*STATE_SCHOOL_FIELDS, raiseload=True),
        )
        .filter(
            or_(Student.national_student_id == ne_sid.strip(), Student.roll_number == ne_sid.strip())
        )
        .one_or_none()
    )
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No student found with roll number {ne_sid}")

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

    # Truancy: any run of 3+ consecutive absences, flagged per entry so the
    # log itself shows which dates form the run.
    truancy_dates: set[str] = set()
    longest_run = 0
    run: list[str] = []

    def close_run(current: list[str]) -> None:
        nonlocal longest_run
        if len(current) >= 3:
            truancy_dates.update(current)
        longest_run = max(longest_run, len(current))

    for row in sorted(attendance_rows, key=lambda a: a.date):
        if row.status == "Absent":
            run.append(row.date.isoformat())
        else:
            close_run(run)
            run = []
    close_run(run)

    # Draft results exist but are withheld by the Exam Data Release Valve.
    total_marks = (
        db.query(func.count(StudentGrade.id)).filter_by(student_id=student.id).scalar()
    )
    withheld_rows = (
        db.query(StudentGrade.exam_name)
        .filter_by(student_id=student.id, is_published=False)
        .distinct()
        .all()
    )
    withheld_exams = sorted({name for (name,) in withheld_rows})

    return {
        "ne_sid": student.national_student_id,
        "roll_number": student.roll_number,
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
            "school_code": school.school_code if school else None,
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
            "longest_absence_run": longest_run,
            "truancy_flag": longest_run >= 3,
            "truancy_dates": len(truancy_dates),
        },
        "attendance_log": [
            {
                "date": a.date.isoformat(),
                "status": a.status,
                "truancy": a.date.isoformat() in truancy_dates,
            }
            for a in attendance_rows[:400]
        ],
        "withheld": {
            "draft_records": int(total_marks or 0) - len(marks),
            "exams": withheld_exams,
            "note": (
                "Draft results are withheld until the school publishes them "
                "(Exam Data Release Valve)."
            ),
        },
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
    schools = (
        db.execute(
            select(PrivateSchool)
            .options(load_only(*STATE_SCHOOL_FIELDS, raiseload=True))
            .order_by(PrivateSchool.school_name)
        )
        .scalars()
        .all()
    )

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
                "school_code": s.school_code,
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

    principal = (
        db.query(User)
        .options(load_only(*STATE_USER_FIELDS, raiseload=True))
        .filter_by(school_id=school_id, role="school_manager", is_active=True)
        .first()
    )
    teachers = (
        db.query(User)
        .options(load_only(*STATE_USER_FIELDS, raiseload=True))
        .filter_by(school_id=school_id, role="teacher", is_active=True)
        .order_by(User.last_name, User.first_name)
        .all()
    )

    student_count = (
        db.query(func.count(Student.id)).filter_by(school_id=school_id, is_active=True).scalar()
    )
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
    assignment_counts = dict(
        db.query(TeachingAssignment.teacher_id, func.count(TeachingAssignment.id))
        .filter(TeachingAssignment.school_id == school_id, TeachingAssignment.teacher_id.is_not(None))
        .group_by(TeachingAssignment.teacher_id)
        .all()
    )

    return {
        "id": school.id,
        "school_name": school.school_name,
        "school_code": school.school_code,
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
        "total_classes": len(classes),
        "classes": [
            {
                "id": klass.id,
                "class_level": klass.class_level,
                "class_stream": klass.class_stream,
                "class_label": f"{klass.class_level} {klass.class_stream}",
                "room_number": klass.room_number,
                "student_count": sum(1 for student in klass.students if student.is_active),
            }
            for klass in classes
        ],
        "teacher_roster": [
            {
                "id": t.id,
                "ne_tid": t.staff_identifier,
                "name": _full_name(t),
                "phone": t.phone,
                "email": t.email,
                "designation": t.designation,
                "assignment_count": int(assignment_counts.get(t.id, 0)),
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
    teacher = (
        db.execute(
            select(User)
            .options(load_only(*STATE_USER_FIELDS, raiseload=True))
            .where(User.id == teacher_id)
        )
        .scalar_one_or_none()
    )
    if not teacher or teacher.role != "teacher":
        raise HTTPException(404, "Teacher not found")

    school = (
        db.execute(
            select(PrivateSchool)
            .options(load_only(*STATE_SCHOOL_FIELDS, raiseload=True))
            .where(PrivateSchool.id == teacher.school_id)
        ).scalar_one_or_none()
        if teacher.school_id
        else None
    )

    # Authoritative schedule assignments — never infer a teacher's role from
    # grade-entry history. A teacher can legitimately enter marks on behalf of
    # another colleague, so TeachingAssignment is the sole source of truth.
    assignment_rows = (
        db.query(TeachingAssignment, SchoolClass, Subject)
        .join(SchoolClass, TeachingAssignment.class_id == SchoolClass.id)
        .join(Subject, TeachingAssignment.subject_id == Subject.id)
        .options(
            joinedload(TeachingAssignment.teacher).load_only(*STATE_USER_FIELDS, raiseload=True)
        )
        .filter(
            TeachingAssignment.school_id == teacher.school_id,
            TeachingAssignment.teacher_id == teacher.id,
        )
        .all()
    )
    assignment_rows.sort(key=lambda row: (class_sort_key(row[1]), row[2].subject_name.casefold(), row[2].id))

    # Homeroom / classroom schedule.
    schedule = (
        db.query(SchoolClass)
        .filter_by(school_id=teacher.school_id, class_teacher_id=teacher.id)
        .all()
    )
    schedule.sort(key=class_sort_key)
    assignments = [
        {
            "assignment_id": assignment.id,
            "class_id": klass.id,
            "class_level": klass.class_level,
            "class_stream": klass.class_stream,
            "class_label": f"{klass.class_level} {klass.class_stream}",
            "subject_id": subject.id,
            "subject_code": subject.subject_code,
            "subject_name": subject.subject_name,
        }
        for assignment, klass, subject in assignment_rows
    ]

    return {
        "id": teacher.id,
        "ne_tid": teacher.staff_identifier,
        "name": _full_name(teacher),
        "email": teacher.email,
        "phone": teacher.phone,
        "qualifications": teacher.qualifications,
        "designation": teacher.designation,
        "bio": teacher.bio,
        "school": {
            "id": school.id if school else None,
            "school_name": school.school_name if school else None,
            "school_code": school.school_code if school else None,
        },
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
                "class_id": c.id,
                "class_level": c.class_level,
                "class_stream": c.class_stream,
                "class_label": f"{c.class_level} {c.class_stream}",
                "room_number": c.room_number,
            }
            for c in schedule
        ],
    }


@router.get("/class-levels")
def class_levels(_user: User = Depends(require_state)):
    """Class 1-12 options for the Live Attendance filter dropdown."""
    return {"class_levels": list(CLASS_LEVELS)}

"""IMPLEMENTATION PHASE 3 — INTERACTIVE QUERY ANALYTICS PLATFORM.

Dialect-portable mirrors of Views A / B / C (the authoritative PostgreSQL
definitions live in sql/003_analytics_views.sql). These feed the API routing
services directly.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import case, func, nulls_last, select
from sqlalchemy.orm import Session

from app.models import (
    DailySubmissionLog,
    ExamSubmissionEvent,
    LiveAttendance,
    PrivateSchool,
    SchoolClass,
    Student,
    StudentGrade,
    Subject,
)

STATUS_RED_ALARM = "🚨 RED ALARM: OVERDUE BY 3+ HOURS"
STATUS_PENDING = "⚠️ PENDING SUBMISSION WINDOW"
STATUS_COMPLIANT = "✅ COMPLIANT"


def view_a_state_compliance_map(database_session: Session) -> list[dict]:
    """View A: State Supervisor Core Command Map & Alarm Portal."""
    today = dt.date.today()
    submitted = func.coalesce(DailySubmissionLog.attendance_submitted, False)
    alarmed = func.coalesce(DailySubmissionLog.alarm_triggered, False)

    rows = database_session.execute(
        select(
            PrivateSchool.id.label("school_id"),
            PrivateSchool.school_name,
            PrivateSchool.state_license_number,
            submitted.label("daily_attendance_logged"),
            DailySubmissionLog.attendance_submitted_at.label("time_received"),
            alarmed.label("is_red_alarm_active"),
        )
        .join(
            DailySubmissionLog,
            (PrivateSchool.id == DailySubmissionLog.school_id)
            & (DailySubmissionLog.log_date == today),
            isouter=True,
        )
        .where(PrivateSchool.accreditation_status == "Active")
        .order_by(nulls_last(alarmed.desc()), nulls_last(submitted.asc()))
    ).all()

    results = []
    for r in rows:
        if r.is_red_alarm_active:
            status = STATUS_RED_ALARM
        elif r.daily_attendance_logged is False:
            status = STATUS_PENDING
        else:
            status = STATUS_COMPLIANT
        results.append(
            {
                "school_id": r.school_id,
                "school_name": r.school_name,
                "state_license_number": r.state_license_number,
                "daily_attendance_logged": bool(r.daily_attendance_logged),
                "time_received": r.time_received.isoformat() if r.time_received else None,
                "is_red_alarm_active": bool(r.is_red_alarm_active),
                "state_compliance_status": status,
            }
        )
    return results


def view_b_student_lookup(database_session: Session, user_query_input: str) -> list[dict]:
    """Query B: Deep Student Directory Search — ILIKE fuzzy match on last_name,
    direct match on national_student_id (plus guardian-number search for the
    State command board bar)."""
    needle = user_query_input.strip()
    if not needle:
        return []
    like_pattern = f"%{needle}%"

    rows = database_session.execute(
        select(
            PrivateSchool.school_name,
            SchoolClass.class_level,
            SchoolClass.class_stream,
            Student.national_student_id,
            Student.first_name,
            Student.last_name,
            Student.guardian_name,
            Student.guardian_relationship,
            Student.guardian_phone,
            Student.guardian_email,
            Student.emergency_contact_phone,
        )
        .join(PrivateSchool, Student.school_id == PrivateSchool.id)
        .join(SchoolClass, Student.current_class_id == SchoolClass.id, isouter=True)
        .where(
            (Student.national_student_id == needle)
            | Student.last_name.ilike(like_pattern)
            | Student.guardian_phone.ilike(like_pattern)
        )
        .order_by(PrivateSchool.school_name, SchoolClass.class_level, Student.last_name)
        .limit(200)
    ).all()

    return [
        {
            "school_name": r.school_name,
            "class_level": r.class_level,
            "class_stream": r.class_stream,
            "national_student_id": r.national_student_id,
            "first_name": r.first_name,
            "last_name": r.last_name,
            "guardian_name": r.guardian_name,
            "guardian_relationship": r.guardian_relationship,
            "guardian_phone": r.guardian_phone,
            "guardian_email": r.guardian_email,
            "emergency_contact_phone": r.emergency_contact_phone,
        }
        for r in rows
    ]


def view_c_grade_analytics(
    database_session: Session,
    *,
    school_id: int | None = None,
    class_level: str | None = None,
) -> list[dict]:
    """Query C: State Subject Benchmarking Index.

    Averages numeric_score across schools for any target class level
    (Class 1 - Class 12). The grade table is filtered so only scores carrying
    a matching publication token event inside exam_submission_events are
    pulled — drafts and un-tokenized rows are structurally excluded.
    """
    # Correlated EXISTS: the release-valve token must be present in the log.
    release_token_exists = (
        select(1)
        .where(
            ExamSubmissionEvent.school_id == StudentGrade.school_id,
            ExamSubmissionEvent.class_id == StudentGrade.class_id,
            ExamSubmissionEvent.subject_id == StudentGrade.subject_id,
            ExamSubmissionEvent.academic_year_id == StudentGrade.academic_year_id,
            ExamSubmissionEvent.exam_name == StudentGrade.exam_name,
        )
        .exists()
    )

    stmt = (
        select(
            PrivateSchool.school_name,
            SchoolClass.class_level,
            Subject.subject_name,
            func.count(StudentGrade.id).label("total_marked_records"),
            func.round(func.avg(StudentGrade.numeric_score), 2).label("structural_average_mark"),
            func.max(StudentGrade.numeric_score).label("peak_score"),
        )
        .join(PrivateSchool, StudentGrade.school_id == PrivateSchool.id)
        .join(SchoolClass, StudentGrade.class_id == SchoolClass.id)
        .join(Subject, StudentGrade.subject_id == Subject.id)
        .where(release_token_exists)
        .group_by(PrivateSchool.school_name, SchoolClass.class_level, Subject.subject_name)
        .order_by(PrivateSchool.school_name, SchoolClass.class_level, Subject.subject_name)
    )
    if school_id is not None:
        stmt = stmt.where(StudentGrade.school_id == school_id)
    if class_level:
        stmt = stmt.where(SchoolClass.class_level == class_level)

    rows = database_session.execute(stmt).all()
    return [
        {
            "school_name": r.school_name,
            "class_level": r.class_level,
            "subject_name": r.subject_name,
            "total_marked_records": int(r.total_marked_records),
            "structural_average_mark": float(r.structural_average_mark) if r.structural_average_mark is not None else None,
            "peak_score": float(r.peak_score) if r.peak_score is not None else None,
        }
        for r in rows
    ]


def state_live_attendance_feed(
    database_session: Session,
    *,
    school_id: int | None,
    target_date: dt.date | None = None,
    class_level: str | None = None,
) -> list[dict]:
    """Read-only state visibility into live attendance logs.

    `class_level` drives the Class 1-12 filter dropdown on the state's live
    attendance monitor.
    """
    target_date = target_date or dt.date.today()
    stmt = (
        select(
            PrivateSchool.school_name,
            SchoolClass.class_level,
            SchoolClass.class_stream,
            Student.national_student_id,
            Student.first_name,
            Student.last_name,
            LiveAttendance.date,
            LiveAttendance.status,
        )
        .join(PrivateSchool, LiveAttendance.school_id == PrivateSchool.id)
        .join(SchoolClass, LiveAttendance.class_id == SchoolClass.id)
        .join(Student, LiveAttendance.student_id == Student.id)
        .where(LiveAttendance.date == target_date)
        .order_by(PrivateSchool.school_name, SchoolClass.class_level, Student.last_name)
        .limit(500)
    )
    if school_id is not None:
        stmt = stmt.where(LiveAttendance.school_id == school_id)
    if class_level is not None:
        stmt = stmt.where(SchoolClass.class_level == class_level)
    rows = database_session.execute(stmt).all()
    return [
        {
            "school_name": r.school_name,
            "class": f"{r.class_level} {r.class_stream}",
            "national_student_id": r.national_student_id,
            "student": f"{r.first_name} {r.last_name}",
            "date": r.date.isoformat(),
            "status": r.status,
        }
        for r in rows
    ]

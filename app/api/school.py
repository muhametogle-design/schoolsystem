"""TENANT ERP ROUTES — classes, students, attendance, marks, publish valve.

All routes are school-scoped: `user.school_id` is injected into every query
so one tenant can never observe another tenant's rows.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_school
from app.core.config import settings
from app.core.db import get_db
from app.core.ws import manager
from app.models import (
    ATTENDANCE_STATUSES,
    CLASS_LEVELS,
    AcademicYear,
    DailySubmissionLog,
    ExamSubmissionEvent,
    LiveAttendance,
    SchoolClass,
    Student,
    StudentGrade,
    Subject,
    User,
)
from app.schemas import (
    AttendanceBulkRequest,
    AttendanceSubmitRequest,
    ClassCreate,
    GradeBulkRequest,
    PublishRequest,
    StudentCreate,
    SubjectCreate,
)
from app.services.compliance import submit_daily_attendance_roster
from app.services.publication import publish_exam_marks
from app.services.student_id import generate_unique_national_student_id

router = APIRouter(prefix="/api/v1/school", tags=["school-erp"])

any_school_user = require_school()
erp_write = require_school("school_manager", "teacher")
manager_only = require_school("school_manager")


def _class_label(klass: SchoolClass | None) -> str | None:
    return f"{klass.class_level} {klass.class_stream}" if klass else None


# --------------------------------------------------------------------------- #
# Overview / compliance status
# --------------------------------------------------------------------------- #
@router.get("/overview")
def overview(user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    from app.models import PrivateSchool

    today = dt.date.today()
    log = db.execute(
        select(DailySubmissionLog).where(
            DailySubmissionLog.school_id == user.school_id, DailySubmissionLog.log_date == today
        )
    ).scalar_one_or_none()
    year = db.execute(select(AcademicYear).where(AcademicYear.is_current == True)).scalar_one_or_none()  # noqa: E712
    school = db.get(PrivateSchool, user.school_id)

    counts = {
        "classes": db.query(SchoolClass).filter_by(school_id=user.school_id).count(),
        "students": db.query(Student).filter_by(school_id=user.school_id, is_active=True).count(),
        "subjects": db.query(Subject).filter_by(school_id=user.school_id).count(),
    }
    return {
        "school_id": user.school_id,
        "school_name": school.school_name if school else None,
        "academic_year": {"id": year.id, "label": year.label} if year else None,
        "today": today.isoformat(),
        "attendance_deadline": settings.attendance_deadline,
        "alarm_audit_time": settings.alarm_audit_time,
        "daily_submission": {
            "attendance_submitted": bool(log.attendance_submitted) if log else False,
            "attendance_submitted_at": log.attendance_submitted_at.isoformat() if log and log.attendance_submitted_at else None,
            "alarm_triggered": bool(log.alarm_triggered) if log else False,
        },
        "counts": counts,
    }


# --------------------------------------------------------------------------- #
# Classes & subjects
# --------------------------------------------------------------------------- #
@router.get("/classes")
def list_classes(user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    rows = (
        db.query(SchoolClass)
        .options(joinedload(SchoolClass.students))
        .filter_by(school_id=user.school_id)
        .order_by(SchoolClass.class_level, SchoolClass.class_stream)
        .all()
    )
    return {
        "classes": [
            {
                "id": c.id,
                "class_level": c.class_level,
                "class_stream": c.class_stream,
                "room_number": c.room_number,
                "class_label": _class_label(c),
                "student_count": sum(1 for s in c.students if s.is_active),
            }
            for c in rows
        ]
    }


@router.post("/classes", status_code=201)
def create_class(payload: ClassCreate, user: User = Depends(erp_write), db: Session = Depends(get_db)):
    if payload.class_level not in CLASS_LEVELS:
        raise HTTPException(422, f"class_level must be one of {list(CLASS_LEVELS)}")
    exists = (
        db.query(SchoolClass)
        .filter_by(
            school_id=user.school_id,
            class_level=payload.class_level,
            class_stream=payload.class_stream,
        )
        .one_or_none()
    )
    if exists:
        raise HTTPException(409, "This class level + stream already exists")
    klass = SchoolClass(
        school_id=user.school_id,
        class_level=payload.class_level,
        class_stream=payload.class_stream,
        room_number=payload.room_number,
    )
    db.add(klass)
    db.commit()
    return {"id": klass.id, "class_label": _class_label(klass)}


@router.get("/subjects")
def list_subjects(
    class_level: str | None = None, user: User = Depends(any_school_user), db: Session = Depends(get_db)
):
    query = db.query(Subject).filter_by(school_id=user.school_id)
    if class_level:
        query = query.filter_by(class_level=class_level)
    rows = query.order_by(Subject.class_level, Subject.subject_name).all()
    return {
        "subjects": [
            {"id": s.id, "subject_code": s.subject_code, "subject_name": s.subject_name, "class_level": s.class_level}
            for s in rows
        ]
    }


@router.post("/subjects", status_code=201)
def create_subject(payload: SubjectCreate, user: User = Depends(erp_write), db: Session = Depends(get_db)):
    if payload.class_level not in CLASS_LEVELS:
        raise HTTPException(422, f"class_level must be one of {list(CLASS_LEVELS)}")
    subject = Subject(school_id=user.school_id, **payload.model_dump())
    db.add(subject)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Subject code already registered for this class level")
    return {"id": subject.id, "subject_name": subject.subject_name}


@router.get("/academic-years")
def academic_years(user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    rows = db.query(AcademicYear).order_by(AcademicYear.start_date.desc()).all()
    return {
        "academic_years": [
            {"id": y.id, "label": y.label, "is_current": y.is_current} for y in rows
        ]
    }


# --------------------------------------------------------------------------- #
# Students (auto STU-YYYY-XY123 national ID)
# --------------------------------------------------------------------------- #
@router.get("/students")
def list_students(
    class_id: int | None = None,
    q: str | None = None,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    query = db.query(Student).options(joinedload(Student.current_class)).filter_by(school_id=user.school_id)
    if class_id:
        query = query.filter_by(current_class_id=class_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Student.last_name.ilike(like))
            | (Student.first_name.ilike(like))
            | (Student.national_student_id.ilike(like))
        )
    rows = query.order_by(Student.last_name, Student.first_name).limit(500).all()
    return {
        "students": [
            {
                "id": s.id,
                "national_student_id": s.national_student_id,
                "first_name": s.first_name,
                "last_name": s.last_name,
                "gender": s.gender,
                "class_label": _class_label(s.current_class),
                "current_class_id": s.current_class_id,
                "guardian_name": s.guardian_name,
                "guardian_phone": s.guardian_phone,
                "is_active": s.is_active,
            }
            for s in rows
        ]
    }


@router.post("/students", status_code=201)
def register_student(payload: StudentCreate, user: User = Depends(erp_write), db: Session = Depends(get_db)):
    klass = (
        db.query(SchoolClass)
        .filter_by(id=payload.current_class_id, school_id=user.school_id)
        .one_or_none()
    )
    if not klass:
        raise HTTPException(404, "Class not found in this school")

    enrollment_year = payload.enrollment_year or str(dt.date.today().year)
    national_id = generate_unique_national_student_id(db, enrollment_year=enrollment_year)

    student = Student(
        school_id=user.school_id,
        national_student_id=national_id,
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
        enrollment_date=dt.date.today(),
        is_active=True,
    )
    db.add(student)
    db.commit()
    return {
        "id": student.id,
        "national_student_id": student.national_student_id,
        "class_label": _class_label(klass),
        "message": f"Student registered with immutable national tracking ID {student.national_student_id}",
    }


# --------------------------------------------------------------------------- #
# Live attendance + mandatory daily roster submission
# --------------------------------------------------------------------------- #
@router.get("/attendance")
def get_attendance(
    date: dt.date | None = None,
    class_id: int = Query(...),
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    date = date or dt.date.today()
    rows = (
        db.query(LiveAttendance)
        .filter_by(school_id=user.school_id, class_id=class_id, date=date)
        .all()
    )
    by_student = {r.student_id: r.status for r in rows}
    return {"date": date.isoformat(), "class_id": class_id, "statuses": by_student, "allowed_statuses": list(ATTENDANCE_STATUSES)}


@router.post("/attendance")
def record_attendance(payload: AttendanceBulkRequest, user: User = Depends(erp_write), db: Session = Depends(get_db)):
    klass = db.query(SchoolClass).filter_by(id=payload.class_id, school_id=user.school_id).one_or_none()
    if not klass:
        raise HTTPException(404, "Class not found in this school")

    valid_ids = {
        s.id
        for s in db.query(Student).filter_by(school_id=user.school_id, current_class_id=klass.id, is_active=True).all()
    }
    for entry in payload.entries:
        if entry.student_id not in valid_ids:
            raise HTTPException(422, f"Student {entry.student_id} is not an active member of this class")

    existing = {
        r.student_id: r
        for r in db.query(LiveAttendance)
        .filter_by(school_id=user.school_id, class_id=klass.id, date=payload.date)
        .all()
    }
    for entry in payload.entries:
        row = existing.get(entry.student_id)
        if row:
            row.status = entry.status
            row.recorded_by = user.id
        else:
            db.add(
                LiveAttendance(
                    school_id=user.school_id,
                    class_id=klass.id,
                    student_id=entry.student_id,
                    date=payload.date,
                    status=entry.status,
                    recorded_by=user.id,
                )
            )
    db.commit()

    # Notify state dashboards that a roster landed (they hold read visibility).
    manager.broadcast_sync(
        "attendance_recorded",
        {"school_id": user.school_id, "class_label": _class_label(klass), "date": payload.date.isoformat()},
    )
    return {"saved": len(payload.entries), "date": payload.date.isoformat(), "class_label": _class_label(klass)}


@router.post("/attendance/submit")
def submit_roster(
    payload: AttendanceSubmitRequest,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    """Hit by the school to seal today's roster before the 12:00 PM deadline."""
    target_date = payload.date or dt.date.today()
    has_rows = (
        db.query(LiveAttendance)
        .filter_by(school_id=user.school_id, date=target_date)
        .count()
    )
    if has_rows == 0:
        raise HTTPException(422, "No attendance entries recorded for this date — record the roster first")

    log = submit_daily_attendance_roster(db, school_id=user.school_id, user_id=user.id, log_date=target_date)
    submitted_at = log.attendance_submitted_at
    now = submitted_at or dt.datetime.now()
    deadline_hour, deadline_minute = (int(p) for p in settings.attendance_deadline.split(":"))
    late = now.hour * 60 + now.minute > deadline_hour * 60 + deadline_minute

    manager.broadcast_sync(
        "attendance_submitted",
        {
            "school_id": user.school_id,
            "date": target_date.isoformat(),
            "submitted_at": submitted_at.isoformat() if submitted_at else None,
            "late": late,
        },
    )
    return {
        "attendance_submitted": True,
        "attendance_submitted_at": submitted_at.isoformat() if submitted_at else None,
        "submitted_after_deadline": late,
        "message": (
            "Roster submitted AFTER the 12:00 PM deadline — recorded as a late submission."
            if late
            else "Roster submitted within the compliance window."
        ),
    }


# --------------------------------------------------------------------------- #
# Continuous assessment marks + THE EXAM DATA RELEASE VALVE
# --------------------------------------------------------------------------- #
@router.get("/grades")
def list_grades(
    class_id: int,
    subject_id: int,
    exam_name: str,
    academic_year_id: int | None = None,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    query = db.query(StudentGrade).filter_by(
        school_id=user.school_id, class_id=class_id, subject_id=subject_id, exam_name=exam_name
    )
    if academic_year_id:
        query = query.filter_by(academic_year_id=academic_year_id)
    rows = query.all()
    published = db.query(ExamSubmissionEvent).filter_by(
        school_id=user.school_id, class_id=class_id, subject_id=subject_id, exam_name=exam_name
    )
    if academic_year_id:
        published = published.filter_by(academic_year_id=academic_year_id)
    event = published.one_or_none()
    return {
        "exam_name": exam_name,
        "is_published": bool(event),
        "publish_event": (
            {"id": event.id, "published_at": event.published_at.isoformat(), "records_released": event.records_released}
            if event
            else None
        ),
        "grades": [
            {"student_id": g.student_id, "numeric_score": float(g.numeric_score), "is_published": g.is_published}
            for g in rows
        ],
    }


@router.post("/grades")
def record_grades(payload: GradeBulkRequest, user: User = Depends(erp_write), db: Session = Depends(get_db)):
    klass = db.query(SchoolClass).filter_by(id=payload.class_id, school_id=user.school_id).one_or_none()
    subject = db.query(Subject).filter_by(id=payload.subject_id, school_id=user.school_id).one_or_none()
    if not klass or not subject:
        raise HTTPException(404, "Class or subject not found in this school")

    event = (
        db.query(ExamSubmissionEvent)
        .filter_by(
            school_id=user.school_id,
            class_id=payload.class_id,
            subject_id=payload.subject_id,
            academic_year_id=payload.academic_year_id,
            exam_name=payload.exam_name,
        )
        .one_or_none()
    )
    if event:
        raise HTTPException(409, "This exam was already published to the State — marks are frozen")

    students = {
        s.id: s
        for s in db.query(Student)
        .filter_by(school_id=user.school_id, current_class_id=payload.class_id, is_active=True)
        .all()
    }
    existing = {
        g.student_id: g
        for g in db.query(StudentGrade).filter_by(
            school_id=user.school_id,
            class_id=payload.class_id,
            subject_id=payload.subject_id,
            academic_year_id=payload.academic_year_id,
            exam_name=payload.exam_name,
        ).all()
    }
    saved = 0
    for entry in payload.entries:
        if entry.student_id not in students:
            raise HTTPException(422, f"Student {entry.student_id} is not in this class")
        row = existing.get(entry.student_id)
        if row:
            if row.is_published:
                raise HTTPException(409, "Cannot modify marks already published to the State")
            row.numeric_score = entry.numeric_score
            row.updated_at = dt.datetime.now()
        else:
            db.add(
                StudentGrade(
                    school_id=user.school_id,
                    student_id=entry.student_id,
                    class_id=payload.class_id,
                    subject_id=payload.subject_id,
                    academic_year_id=payload.academic_year_id,
                    exam_name=payload.exam_name,
                    numeric_score=entry.numeric_score,
                    is_published=False,
                    recorded_by=user.id,
                )
            )
        saved += 1
    db.commit()
    return {"saved": saved, "visibility": "PRIVATE DRAFT — hidden from the State until published"}


@router.post("/grades/publish")
def publish_marks(payload: PublishRequest, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    """📌 THE 'Publish Exam Marks to State' BUTTON (school administrators only)."""
    result = publish_exam_marks(
        db,
        school_id=user.school_id,
        class_id=payload.class_id,
        subject_id=payload.subject_id,
        academic_year_id=payload.academic_year_id,
        exam_name=payload.exam_name,
        published_by=user.id,
    )
    result["message"] = "Exam marks released to the State analytics portal. This action is immutable."
    return result


@router.get("/exam-events")
def own_exam_events(user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    rows = (
        db.query(ExamSubmissionEvent)
        .filter_by(school_id=user.school_id)
        .order_by(ExamSubmissionEvent.published_at.desc())
        .limit(100)
        .all()
    )
    return {
        "events": [
            {
                "id": e.id,
                "class_id": e.class_id,
                "subject_id": e.subject_id,
                "exam_name": e.exam_name,
                "records_released": e.records_released,
                "published_at": e.published_at.isoformat() if e.published_at else None,
            }
            for e in rows
        ]
    }

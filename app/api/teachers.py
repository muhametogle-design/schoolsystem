"""Refinements 2 & 3 — teacher portal: schedule, subject-restricted roster.

The timetable matrix is the single source of authority for what a teacher may
mark: every roster read/write validates that a ``timetable_slots`` row ties
the signed-in teacher to that (class, subject, day, period). Managers keep
full access through the classic attendance workspace; teachers are physically
unable to reach another staff member's registers through these endpoints.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_school
from app.core.config import settings
from app.core.db import get_db
from app.core.ws import manager as websocket_manager
from app.models import (
    ATTENDANCE_STATUSES,
    SchoolClass,
    Student,
    Subject,
    SubjectAttendance,
    TimetableSlot,
    User,
)
from app.schemas import TeacherRosterSave

router = APIRouter(prefix="/api/v1/school/teachers/me", tags=["teacher-portal"])

teacher_only = require_school("teacher")

#: Period clock windows (24h) used to highlight the active period. Keep in
#: sync with the labels shown in the substitution coverage panel.
PERIOD_WINDOWS: dict[int, tuple[str, str]] = {
    1: ("08:00", "08:50"),
    2: ("09:00", "09:50"),
    3: ("10:30", "11:20"),
    4: ("11:30", "12:20"),
    5: ("13:00", "13:50"),
    6: ("14:00", "14:50"),
    7: ("15:00", "15:50"),
    8: ("16:00", "16:50"),
}


def _display_name(user: User | None) -> str | None:
    if not user:
        return None
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or user.email


def _now_in_tz() -> dt.time:
    """Current wall-clock time in the platform timezone."""
    from zoneinfo import ZoneInfo

    now = dt.datetime.now(ZoneInfo(settings.platform_timezone))
    return now.time().replace(second=0, microsecond=0)


def _active_period(now: dt.time | None = None) -> int | None:
    now = now or _now_in_tz()
    minutes = now.hour * 60 + now.minute
    for period, (start, end) in PERIOD_WINDOWS.items():
        sh, sm = (int(v) for v in start.split(":"))
        eh, em = (int(v) for v in end.split(":"))
        if sh * 60 + sm <= minutes <= eh * 60 + em:
            return period
    return None


def _owned_slot(
    db: Session, *, school_id: int, teacher_id: int, date: dt.date,
    class_id: int, subject_id: int, period_number: int,
) -> TimetableSlot:
    """The timetable slot binding this teacher to the requested register.

    Raises 403 when the teacher does not own the (class, subject, period) —
    this is the hard RBAC wall of the marking engine.
    """
    slot = db.execute(
        select(TimetableSlot).where(
            TimetableSlot.school_id == school_id,
            TimetableSlot.teacher_id == teacher_id,
            TimetableSlot.class_id == class_id,
            TimetableSlot.subject_id == subject_id,
            TimetableSlot.day_of_week == date.weekday(),
            TimetableSlot.period_number == period_number,
        )
    ).scalar_one_or_none()
    if not slot:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This register belongs to another teacher's timetable slot — "
            "you can only mark the subjects and periods assigned to you",
        )
    return slot


def _slot_payload(
    db: Session,
    slot: TimetableSlot,
    *,
    date: dt.date,
    active_period: int | None,
) -> dict:
    klass = db.get(SchoolClass, int(slot.class_id))
    subject = db.get(Subject, int(slot.subject_id))
    roster_size = len(
        db.execute(
            select(Student.id).where(
                Student.school_id == slot.school_id,
                Student.current_class_id == slot.class_id,
                Student.is_active.is_(True),
            )
        ).all()
    )
    marked = len(
        db.execute(
            select(SubjectAttendance.id).where(
                SubjectAttendance.school_id == slot.school_id,
                SubjectAttendance.date == date,
                SubjectAttendance.subject_id == slot.subject_id,
                SubjectAttendance.period_number == slot.period_number,
            )
        ).all()
    )
    period = int(slot.period_number)
    start, end = PERIOD_WINDOWS.get(period, ("", ""))
    return {
        "slot_id": int(slot.id),
        "date": date.isoformat(),
        "day_label": date.strftime("%a"),
        "period_number": period,
        "period_label": f"Period {period} · {start}–{end}" if start else f"Period {period}",
        "is_active_period": active_period is not None and period == active_period,
        "class_id": int(slot.class_id),
        "class_label": f"{klass.class_level} {klass.class_stream}" if klass else None,
        "subject_id": int(slot.subject_id),
        "subject_code": subject.subject_code if subject else None,
        "subject_name": subject.subject_name if subject else None,
        "roster_size": roster_size,
        "marked_count": marked,
        "marked_complete": roster_size > 0 and marked >= roster_size,
    }


@router.get("/schedule")
def my_schedule(
    date: dt.date | None = None,
    user: User = Depends(teacher_only),
    db: Session = Depends(get_db),
):
    """The signed-in teacher's subject schedule for a date (today default).

    Slots are ordered by period with the currently-active period highlighted,
    ready for the quick 'Mark Present / Absent / Late' rosters.
    """
    target = date or dt.date.today()
    active_period = _active_period() if target == dt.date.today() else None
    slots = (
        db.execute(
            select(TimetableSlot).where(
                TimetableSlot.school_id == user.school_id,
                TimetableSlot.teacher_id == user.id,
                TimetableSlot.day_of_week == target.weekday(),
            )
        )
        .scalars()
        .all()
    )
    payload = [
        _slot_payload(db, slot, date=target, active_period=active_period)
        for slot in sorted(slots, key=lambda s: s.period_number)
    ]
    return {
        "teacher": {
            "id": int(user.id),
            "name": _display_name(user),
            "staff_identifier": user.staff_identifier,
            "is_department_head": bool(user.is_department_head),
        },
        "date": target.isoformat(),
        "active_period": active_period,
        "period_windows": {str(k): list(v) for k, v in PERIOD_WINDOWS.items()},
        "slots": payload,
        "pending_slots": sum(1 for s in payload if not s["marked_complete"]),
    }


@router.get("/roster")
def get_roster(
    class_id: int = Query(...),
    subject_id: int = Query(...),
    period_number: int = Query(..., ge=1, le=8),
    date: dt.date | None = None,
    user: User = Depends(teacher_only),
    db: Session = Depends(get_db),
):
    """Student roster with saved statuses for one of the teacher's own slots."""
    target = date or dt.date.today()
    _owned_slot(
        db,
        school_id=user.school_id,
        teacher_id=user.id,
        date=target,
        class_id=class_id,
        subject_id=subject_id,
        period_number=period_number,
    )
    klass = db.get(SchoolClass, class_id)
    subject = db.get(Subject, subject_id)
    students = (
        db.execute(
            select(Student)
            .where(
                Student.school_id == user.school_id,
                Student.current_class_id == class_id,
                Student.is_active.is_(True),
            )
            .order_by(Student.roll_number)
        )
        .scalars()
        .all()
    )
    saved = {
        int(row[0]): str(row[1])
        for row in db.execute(
            select(SubjectAttendance.student_id, SubjectAttendance.status).where(
                SubjectAttendance.school_id == user.school_id,
                SubjectAttendance.date == target,
                SubjectAttendance.subject_id == subject_id,
                SubjectAttendance.period_number == period_number,
            )
        ).all()
    }
    return {
        "date": target.isoformat(),
        "class_id": class_id,
        "class_label": f"{klass.class_level} {klass.class_stream}" if klass else None,
        "subject_id": subject_id,
        "subject_name": subject.subject_name if subject else None,
        "period_number": period_number,
        "allowed_statuses": list(ATTENDANCE_STATUSES),
        "students": [
            {
                "student_id": int(student.id),
                "roll_number": student.roll_number,
                "name": f"{student.first_name} {student.last_name}",
                "status": saved.get(int(student.id)),
            }
            for student in students
        ],
        "marked_count": sum(1 for student in students if int(student.id) in saved),
    }


@router.post("/roster")
def save_roster(
    payload: TeacherRosterSave,
    user: User = Depends(teacher_only),
    db: Session = Depends(get_db),
):
    """Mark Present / Absent / Late for one own subject period (upsert)."""
    target = payload.date or dt.date.today()
    _owned_slot(
        db,
        school_id=user.school_id,
        teacher_id=user.id,
        date=target,
        class_id=payload.class_id,
        subject_id=payload.subject_id,
        period_number=payload.period_number,
    )

    klass = db.get(SchoolClass, payload.class_id)
    if not klass or klass.school_id != user.school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found in this school")
    valid_ids = {
        int(s)
        for s in db.execute(
            select(Student.id).where(
                Student.school_id == user.school_id,
                Student.current_class_id == payload.class_id,
                Student.is_active.is_(True),
            )
        ).scalars().all()
    }
    existing = {
        int(row[0]): row
        for row in db.execute(
            select(SubjectAttendance.student_id, SubjectAttendance).where(
                SubjectAttendance.school_id == user.school_id,
                SubjectAttendance.date == target,
                SubjectAttendance.subject_id == payload.subject_id,
                SubjectAttendance.period_number == payload.period_number,
            )
        ).all()
    }
    saved = 0
    for entry in payload.entries:
        if entry.student_id not in valid_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Student {entry.student_id} is not an active member of this class",
            )
        row = existing.get(entry.student_id)
        if row is not None:
            attendance = row[1]
            attendance.status = entry.status
            attendance.recorded_by = user.id
        else:
            db.add(
                SubjectAttendance(
                    school_id=user.school_id,
                    class_id=payload.class_id,
                    subject_id=payload.subject_id,
                    period_number=payload.period_number,
                    student_id=entry.student_id,
                    date=target,
                    status=entry.status,
                    recorded_by=user.id,
                )
            )
        saved += 1
    db.commit()
    websocket_manager.broadcast_sync(
        "subject_attendance_marked",
        {
            "school_id": user.school_id,
            "class_id": payload.class_id,
            "subject_id": payload.subject_id,
            "period_number": payload.period_number,
            "date": target.isoformat(),
            "saved": saved,
            "by": _display_name(user),
        },
    )
    return {"saved": saved, "date": target.isoformat(), "period_number": payload.period_number}

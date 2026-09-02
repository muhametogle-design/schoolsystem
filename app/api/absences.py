"""Module 1 API — teacher absence logging and the real-time coverage panel.

Every route is tenant-scoped. Managers and teachers can log absences and
confirm recommendations; the matching engine itself lives in
``app.services.substitution``.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_school
from app.core.db import get_db
from app.core.ws import manager as websocket_manager
from app.models import (
    SchoolClass,
    Subject,
    SubstitutionAssignment,
    TeacherAbsence,
    TimetableSlot,
    User,
)
from app.schemas import AbsenceCreate, SubstitutionConfirm
from app.services import substitution
from app.services.substitution import WEEKDAY_LABELS, recommendation_payload

router = APIRouter(prefix="/api/v1/school", tags=["substitution-engine"])

erp_write = require_school("school_manager", "teacher")
any_school_user = require_school()


def _display_name(user: User | None) -> str | None:
    if not user:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def _absence_payload(db: Session, absence: TeacherAbsence, *, with_panel: bool = False) -> dict:
    teacher = db.get(User, int(absence.teacher_id))
    substitutions = (
        db.execute(
            select(SubstitutionAssignment).where(SubstitutionAssignment.absence_id == absence.id)
        )
        .scalars()
        .all()
    )
    class_map = {
        int(c.id): c for c in db.execute(select(SchoolClass).where(SchoolClass.school_id == absence.school_id)).scalars().all()
    }
    subject_map = {
        int(s.id): s for s in db.execute(select(Subject).where(Subject.school_id == absence.school_id)).scalars().all()
    }
    user_map = {
        int(u.id): u
        for u in db.execute(select(User).where(User.school_id == absence.school_id)).scalars().all()
    }
    return {
        "absence_id": int(absence.id),
        "teacher_id": int(absence.teacher_id),
        "teacher_name": _display_name(teacher),
        "absence_date": absence.absence_date.isoformat(),
        "day_label": WEEKDAY_LABELS[absence.absence_date.weekday()],
        "reason": absence.reason,
        "status": absence.status,
        "created_at": absence.created_at.isoformat() if absence.created_at else None,
        "substitutions": [
            {
                "id": int(sub.id),
                "period_number": int(sub.period_number),
                "class_label": (
                    f"{class_map[sub.class_id].class_level} {class_map[sub.class_id].class_stream}"
                    if sub.class_id in class_map
                    else None
                ),
                "subject_name": subject_map[sub.subject_id].subject_name if sub.subject_id in subject_map else None,
                "substitute_teacher_id": int(sub.substitute_teacher_id) if sub.substitute_teacher_id else None,
                "substitute_name": _display_name(user_map.get(sub.substitute_teacher_id)),
                "status": sub.status,
                "match_score": sub.match_score,
                "match_reason": sub.match_reason,
            }
            for sub in substitutions
        ],
        **({"panel": recommendation_payload(db, absence)} if with_panel else {}),
    }


@router.get("/absences")
def list_absences(
    date: str | None = None,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    query = (
        select(TeacherAbsence)
        .where(TeacherAbsence.school_id == user.school_id)
        .order_by(TeacherAbsence.absence_date.desc(), TeacherAbsence.id.desc())
        .limit(100)
    )
    if date:
        try:
            query = query.where(TeacherAbsence.absence_date == dt.date.fromisoformat(date))
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "date must be YYYY-MM-DD") from exc
    absences = db.execute(query).scalars().all()
    return {"absences": [_absence_payload(db, absence) for absence in absences]}


@router.post("/absences", status_code=status.HTTP_201_CREATED)
def log_absence(
    payload: AbsenceCreate,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    """Log an absence — this arms the coverage recommendation engine."""
    teacher = db.execute(
        select(User).where(
            User.id == payload.teacher_id,
            User.school_id == user.school_id,
            User.role == "teacher",
        )
    ).scalar_one_or_none()
    if not teacher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Teacher not found in this school")

    absence_date = payload.absence_date or dt.date.today()
    existing = db.execute(
        select(TeacherAbsence).where(
            TeacherAbsence.school_id == user.school_id,
            TeacherAbsence.teacher_id == teacher.id,
            TeacherAbsence.absence_date == absence_date,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An absence is already logged for this teacher on that date",
        )

    absence = TeacherAbsence(
        school_id=user.school_id,
        teacher_id=teacher.id,
        absence_date=absence_date,
        reason=payload.reason,
        status="logged",
        logged_by=user.id,
    )
    db.add(absence)
    db.commit()

    panel = recommendation_payload(db, absence)
    websocket_manager.broadcast_sync(
        "absence_logged",
        {
            "school_id": user.school_id,
            "absence_id": int(absence.id),
            "teacher": _display_name(teacher),
            "date": absence_date.isoformat(),
            "slots_uncovered": panel["slots_uncovered"],
        },
    )
    return {"absence": _absence_payload(db, absence, with_panel=True), "panel": panel}


@router.get("/absences/{absence_id}/recommendations")
def get_recommendations(
    absence_id: int,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Recompute the coverage panel in real time (fresh availability state)."""
    absence = db.execute(
        select(TeacherAbsence).where(
            TeacherAbsence.id == absence_id, TeacherAbsence.school_id == user.school_id
        )
    ).scalar_one_or_none()
    if not absence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Absence not found")
    if absence.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "This absence was cancelled")
    return recommendation_payload(db, absence)


@router.post("/absences/{absence_id}/auto-assign")
def auto_assign(
    absence_id: int,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    """One-click: confirm the best-ranked candidate for every open slot."""
    absence = db.execute(
        select(TeacherAbsence).where(
            TeacherAbsence.id == absence_id, TeacherAbsence.school_id == user.school_id
        )
    ).scalar_one_or_none()
    if not absence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Absence not found")
    if absence.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "This absence was cancelled")

    created = substitution.auto_assign_best(db, absence, assigned_by=user.id)
    db.commit()
    panel = recommendation_payload(db, absence)
    websocket_manager.broadcast_sync(
        "substitution_assigned",
        {
            "school_id": user.school_id,
            "absence_id": int(absence.id),
            "auto": True,
            "assigned": len(created),
        },
    )
    return {"absence": _absence_payload(db, absence), "panel": panel, "assigned": len(created)}


@router.post("/substitutions", status_code=status.HTTP_201_CREATED)
def confirm_substitution(
    payload: SubstitutionConfirm,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    """Confirm one recommended candidate for one absent slot."""
    absence = db.execute(
        select(TeacherAbsence).where(
            TeacherAbsence.id == payload.absence_id,
            TeacherAbsence.school_id == user.school_id,
        )
    ).scalar_one_or_none()
    if not absence or absence.status == "cancelled":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Absence not found")

    substitute = db.execute(
        select(User).where(
            User.id == payload.substitute_teacher_id,
            User.school_id == user.school_id,
            User.role == "teacher",
            User.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if not substitute:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Substitute teacher not found in this school")

    panel = recommendation_payload(db, absence)
    slot = next(
        (
            s
            for s in panel["slots"]
            if s["period_number"] == payload.period_number and s["class_id"] == payload.class_id
        ),
        None,
    )
    if not slot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That period is not part of the absent teacher's day")
    if slot["covered"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot already has a confirmed substitute")

    best = next((c for c in slot["candidates"] if c["teacher_id"] == payload.substitute_teacher_id), None)
    if best is None:
        # Not in the shortlist (busy/absent) — reject to protect timetable integrity.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Candidate is unavailable for this period (busy or absent)",
        )

    assignment = SubstitutionAssignment(
        school_id=user.school_id,
        absence_id=absence.id,
        class_id=slot["class_id"],
        subject_id=slot["subject_id"],
        original_teacher_id=absence.teacher_id,
        substitute_teacher_id=substitute.id,
        day_of_week=absence.absence_date.weekday(),
        date_for_day=absence.absence_date,
        period_number=slot["period_number"],
        status="confirmed",
        match_score=best["score"],
        match_reason="; ".join(best["reasons"]) or "Manual confirmation",
        assigned_by=user.id,
    )
    db.add(assignment)
    substitution._refresh_absence_status(db, absence)
    db.commit()
    websocket_manager.broadcast_sync(
        "substitution_assigned",
        {
            "school_id": user.school_id,
            "absence_id": int(absence.id),
            "substitute": _display_name(substitute),
            "period": slot["period_number"],
        },
    )
    return {"absence": _absence_payload(db, absence), "panel": recommendation_payload(db, absence)}


@router.delete("/absences/{absence_id}", status_code=status.HTTP_200_OK)
def cancel_absence(
    absence_id: int,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    absence = db.execute(
        select(TeacherAbsence).where(
            TeacherAbsence.id == absence_id, TeacherAbsence.school_id == user.school_id
        )
    ).scalar_one_or_none()
    if not absence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Absence not found")
    absence.status = "cancelled"
    absence.resolved_at = dt.datetime.now()
    db.commit()
    return {"absence": _absence_payload(db, absence)}


@router.get("/timetable")
def get_timetable(
    day: int | None = None,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Weekly timetable grid (optionally one ISO weekday 0=Mon)."""
    query = (
        select(TimetableSlot)
        .where(TimetableSlot.school_id == user.school_id)
        .order_by(TimetableSlot.day_of_week, TimetableSlot.period_number)
    )
    if day is not None:
        if not 0 <= int(day) <= 6:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "day must be 0 (Mon) .. 6 (Sun)")
        query = query.where(TimetableSlot.day_of_week == int(day))

    slots = db.execute(query).scalars().all()
    class_map = {
        int(c.id): c for c in db.execute(select(SchoolClass).where(SchoolClass.school_id == user.school_id)).scalars().all()
    }
    subject_map = {
        int(s.id): s for s in db.execute(select(Subject).where(Subject.school_id == user.school_id)).scalars().all()
    }
    user_map = {
        int(u.id): u for u in db.execute(select(User).where(User.school_id == user.school_id)).scalars().all()
    }
    return {
        "days": list(WEEKDAY_LABELS),
        "slots": [
            {
                "id": int(slot.id),
                "day_of_week": int(slot.day_of_week),
                "day_label": WEEKDAY_LABELS[slot.day_of_week],
                "period_number": int(slot.period_number),
                "class_id": int(slot.class_id),
                "class_label": (
                    f"{class_map[slot.class_id].class_level} {class_map[slot.class_id].class_stream}"
                    if slot.class_id in class_map
                    else None
                ),
                "subject_id": int(slot.subject_id),
                "subject_name": subject_map[slot.subject_id].subject_name if slot.subject_id in subject_map else None,
                "teacher_id": int(slot.teacher_id),
                "teacher_name": _display_name(user_map.get(slot.teacher_id)),
            }
            for slot in slots
        ],
    }


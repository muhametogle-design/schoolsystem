"""Module 2 API — syllabus completion tracking across Classes 1-12.

Teachers and managers record progress checkpoints; managers set the midterm
and final benchmark gates. The summary endpoint powers the tracker board with
computed percentages and 'On Track' / 'Ahead' / 'Behind Schedule' tags.
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
    CLASS_LEVELS,
    SchoolClass,
    Subject,
    SyllabusPlan,
    SyllabusProgressEntry,
    User,
)
from app.schemas import SyllabusBenchmarkUpdate, SyllabusPlanCreate, SyllabusProgressCreate
from app.services.syllabus import (
    default_term_window,
    plan_progress_payload,
    record_progress,
    syllabus_summary,
)

router = APIRouter(prefix="/api/v1/school/syllabus", tags=["syllabus-tracker"])

erp_write = require_school("school_manager", "teacher")
manager_only = require_school("school_manager")
any_school_user = require_school()


def _load_plan(db: Session, school_id: int, plan_id: int) -> SyllabusPlan:
    plan = db.execute(
        select(SyllabusPlan).where(
            SyllabusPlan.id == plan_id, SyllabusPlan.school_id == school_id
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Syllabus plan not found")
    return plan


@router.get("/summary")
def get_summary(
    class_level: str | None = None,
    term: str | None = None,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Tracker board: per-subject progress %, benchmark gates, status tags."""
    if class_level and class_level not in CLASS_LEVELS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown class level: {class_level}")
    return syllabus_summary(db, user.school_id, class_level=class_level, term=term)


@router.get("/plans/{plan_id}")
def get_plan(
    plan_id: int,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    plan = _load_plan(db, user.school_id, plan_id)
    entries = db.execute(
        select(SyllabusProgressEntry)
        .where(SyllabusProgressEntry.plan_id == plan.id)
        .order_by(SyllabusProgressEntry.entry_date.desc(), SyllabusProgressEntry.id.desc())
        .limit(50)
    ).scalars().all()
    return {
        "plan": plan_progress_payload(db, plan),
        "entries": [
            {
                "id": int(entry.id),
                "entry_date": entry.entry_date.isoformat(),
                "units_after": int(entry.units_after),
                "note": entry.note,
                "recorded_by": int(entry.recorded_by) if entry.recorded_by else None,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }
            for entry in entries
        ],
    }


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: SyllabusPlanCreate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    klass = db.execute(
        select(SchoolClass).where(
            SchoolClass.id == payload.class_id, SchoolClass.school_id == user.school_id
        )
    ).scalar_one_or_none()
    if not klass:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found in this school")
    subject = db.execute(
        select(Subject).where(
            Subject.id == payload.subject_id, Subject.school_id == user.school_id
        )
    ).scalar_one_or_none()
    if not subject:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found in this school")

    start, midterm, end = default_term_window()
    duplicate = db.execute(
        select(SyllabusPlan).where(
            SyllabusPlan.school_id == user.school_id,
            SyllabusPlan.class_id == payload.class_id,
            SyllabusPlan.subject_id == payload.subject_id,
            SyllabusPlan.term == payload.term,
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, "A plan for this class/subject/term already exists")

    plan = SyllabusPlan(
        school_id=user.school_id,
        class_id=klass.id,
        subject_id=subject.id,
        term=payload.term,
        total_units=payload.total_units,
        midterm_target_pct=payload.midterm_target_pct,
        final_target_pct=payload.final_target_pct,
        term_start=payload.term_start or start,
        midterm_date=payload.midterm_date or midterm,
        term_end=payload.term_end or end,
        created_by=user.id,
    )
    db.add(plan)
    db.commit()
    websocket_manager.broadcast_sync(
        "syllabus_plan_created",
        {"school_id": user.school_id, "plan_id": int(plan.id), "class": klass.class_level},
    )
    return {"plan": plan_progress_payload(db, plan)}


@router.put("/plans/{plan_id}/benchmarks")
def update_benchmarks(
    plan_id: int,
    payload: SyllabusBenchmarkUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """Set/adjust the midterm & final exam benchmark gates."""
    plan = _load_plan(db, user.school_id, plan_id)
    if payload.midterm_target_pct is not None:
        plan.midterm_target_pct = payload.midterm_target_pct
    if payload.final_target_pct is not None:
        plan.final_target_pct = payload.final_target_pct
    if payload.term_start is not None:
        plan.term_start = payload.term_start
    if payload.midterm_date is not None:
        plan.midterm_date = payload.midterm_date
    if payload.term_end is not None:
        plan.term_end = payload.term_end
    db.commit()
    websocket_manager.broadcast_sync(
        "syllabus_benchmarks_updated",
        {"school_id": user.school_id, "plan_id": int(plan.id)},
    )
    return {"plan": plan_progress_payload(db, plan)}


@router.post("/plans/{plan_id}/progress", status_code=status.HTTP_201_CREATED)
def add_progress(
    plan_id: int,
    payload: SyllabusProgressCreate,
    user: User = Depends(erp_write),
    db: Session = Depends(get_db),
):
    """Record an audited progress checkpoint (units completed to date)."""
    plan = _load_plan(db, user.school_id, plan_id)
    entry_date = payload.entry_date or dt.date.today()
    entry = record_progress(
        db,
        plan,
        entry_date=entry_date,
        units_after=payload.units_after,
        recorded_by=user.id,
        note=payload.note,
    )
    db.commit()
    result = plan_progress_payload(db, plan)
    websocket_manager.broadcast_sync(
        "syllabus_progress",
        {
            "school_id": user.school_id,
            "plan_id": int(plan.id),
            "completion_pct": result["completion_pct"],
            "status": result["status"],
        },
    )
    return {"entry_id": int(entry.id), "plan": result}

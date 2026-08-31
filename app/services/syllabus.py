"""Module 2 — Syllabus completion tracker (Classes 1-12).

Pace engine: for every class/subject plan the expected completion percentage
is interpolated between three anchored gates — term start (0%), the midterm
benchmark, and the final benchmark. Actual completion is the latest audited
progress checkpoint. The gap drives the status tag:

* ``Ahead``            — actual >= expected + AHEAD_MARGIN
* ``Behind Schedule``  — actual <  expected - BEHIND_MARGIN
* ``On Track``         — anything inside the tolerance band
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CLASS_LEVELS,
    SchoolClass,
    Subject,
    SyllabusPlan,
    SyllabusProgressEntry,
)

AHEAD_MARGIN_PCT = 5.0
BEHIND_MARGIN_PCT = 5.0

STATUS_ON_TRACK = "On Track"
STATUS_AHEAD = "Ahead"
STATUS_BEHIND = "Behind Schedule"


def clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def completed_units(db: Session, plan_id: int) -> int:
    """Authoritative completed units = latest checkpoint (date, then id)."""
    entry = db.execute(
        select(SyllabusProgressEntry)
        .where(SyllabusProgressEntry.plan_id == plan_id)
        .order_by(SyllabusProgressEntry.entry_date.desc(), SyllabusProgressEntry.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return int(entry.units_after) if entry else 0


def expected_completion_pct(plan: SyllabusPlan, on_date: dt.date | None = None) -> float:
    """Piecewise-linear expected completion for a date.

    term_start -> midterm_date ramps 0% -> midterm_target_pct; midterm_date ->
    term_end ramps midterm_target_pct -> final_target_pct. Before term start
    the expectation is 0; after term end it is the final target.
    """
    on_date = on_date or dt.date.today()
    start, midterm, end = plan.term_start, plan.midterm_date, plan.term_end
    midterm_target = float(plan.midterm_target_pct or 0)
    final_target = float(plan.final_target_pct or 100)

    if start and end and end <= start:
        # Degenerate window: fall back to the final target immediately.
        return clamp_pct(final_target)
    if start is None or on_date < start:
        return 0.0
    if end is not None and on_date >= end:
        return clamp_pct(final_target)

    if midterm and on_date < midterm and start <= midterm:
        span = (midterm - start).days or 1
        progress = (on_date - start).days / span
        return clamp_pct(midterm_target * progress)

    anchor = midterm or start
    anchor_target = midterm_target if midterm else 0.0
    if end is None:
        return clamp_pct(anchor_target)
    span = (end - anchor).days or 1
    progress = min(1.0, max(0.0, (on_date - anchor).days / span))
    return clamp_pct(anchor_target + (final_target - anchor_target) * progress)


def classify_status(actual_pct: float, expected_pct: float) -> str:
    if actual_pct >= expected_pct + AHEAD_MARGIN_PCT:
        return STATUS_AHEAD
    if actual_pct < expected_pct - BEHIND_MARGIN_PCT:
        return STATUS_BEHIND
    return STATUS_ON_TRACK


def plan_progress_payload(
    db: Session, plan: SyllabusPlan, on_date: dt.date | None = None
) -> dict:
    """Serializer with computed progress, benchmark gates and status tag."""
    on_date = on_date or dt.date.today()
    units = completed_units(db, int(plan.id))
    total = int(plan.total_units or 1)
    actual_pct = clamp_pct(units / total * 100.0)
    expected_pct = expected_completion_pct(plan, on_date)
    status = classify_status(actual_pct, expected_pct)

    klass, subject = plan.school_class, plan.subject
    return {
        "plan_id": int(plan.id),
        "class_id": int(plan.class_id),
        "class_level": klass.class_level if klass else None,
        "class_stream": klass.class_stream if klass else None,
        "class_label": f"{klass.class_level} {klass.class_stream}" if klass else None,
        "subject_id": int(plan.subject_id),
        "subject_code": subject.subject_code if subject else None,
        "subject_name": subject.subject_name if subject else None,
        "term": plan.term,
        "total_units": int(plan.total_units),
        "units_completed": units,
        "completion_pct": round(actual_pct, 1),
        "expected_pct": round(expected_pct, 1),
        "midterm_target_pct": float(plan.midterm_target_pct),
        "final_target_pct": float(plan.final_target_pct),
        "midterm_date": plan.midterm_date.isoformat() if plan.midterm_date else None,
        "term_start": plan.term_start.isoformat() if plan.term_start else None,
        "term_end": plan.term_end.isoformat() if plan.term_end else None,
        "status": status,
        "flagged": status == STATUS_BEHIND,
    }


def syllabus_summary(
    db: Session,
    school_id: int,
    *,
    class_level: str | None = None,
    term: str | None = None,
    on_date: dt.date | None = None,
) -> dict:
    """Classes 1-12 tracker overview: every plan with computed status tags."""
    query = (
        select(SyllabusPlan)
        .where(SyllabusPlan.school_id == school_id)
        .order_by(SyllabusPlan.class_id, SyllabusPlan.subject_id)
    )
    if term:
        query = query.where(SyllabusPlan.term == term)

    plans = db.execute(query).scalars().all()

    levels_order = {level: index for index, level in enumerate(CLASS_LEVELS)}
    rows = [plan_progress_payload(db, plan, on_date) for plan in plans]
    if class_level:
        rows = [row for row in rows if row["class_level"] == class_level]
    rows.sort(
        key=lambda row: (
            levels_order.get(row["class_level"] or "", 99),
            row["class_stream"] or "",
            row["subject_name"] or "",
        )
    )

    counts = {STATUS_ON_TRACK: 0, STATUS_AHEAD: 0, STATUS_BEHIND: 0}
    for row in rows:
        counts[row["status"]] += 1
    average = round(sum(row["completion_pct"] for row in rows) / len(rows), 1) if rows else 0.0

    available_levels = sorted(
        {row["class_level"] for row in rows if row["class_level"]},
        key=lambda level: levels_order.get(level, 99),
    )
    return {
        "on_date": (on_date or dt.date.today()).isoformat(),
        "term": term,
        "rows": rows,
        "counts": counts,
        "average_completion_pct": average,
        "flagged_count": counts[STATUS_BEHIND],
        "class_levels_available": available_levels,
        "all_class_levels": list(CLASS_LEVELS),
    }


def record_progress(
    db: Session,
    plan: SyllabusPlan,
    *,
    entry_date: dt.date,
    units_after: int,
    recorded_by: int | None,
    note: str | None = None,
) -> SyllabusProgressEntry:
    """Append an audited progress checkpoint (validated, clamped to plan)."""
    units_after = max(0, min(int(units_after), int(plan.total_units)))
    entry = SyllabusProgressEntry(
        plan_id=int(plan.id),
        school_id=plan.school_id,
        entry_date=entry_date,
        units_after=units_after,
        note=note,
        recorded_by=recorded_by,
    )
    db.add(entry)
    db.flush()
    return entry


def default_term_window(today: dt.date | None = None) -> tuple[dt.date, dt.date, dt.date]:
    """Sane default (start, midterm, end) anchored around today."""
    today = today or dt.date.today()
    return today - dt.timedelta(days=45), today + dt.timedelta(days=15), today + dt.timedelta(days=75)


def count_plans(db: Session, school_id: int) -> int:
    return int(
        db.execute(
            select(func.count(SyllabusPlan.id)).where(SyllabusPlan.school_id == school_id)
        ).scalar_one()
    )

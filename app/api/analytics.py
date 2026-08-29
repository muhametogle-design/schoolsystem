"""NE-EMIS school analytics — KPI cards, fee matrix, performance & attendance.

Mounted under the tenant ERP prefix. Financial figures (fee collection) are
manager-only, consistent with the rest of the private billing tier.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.deps import require_school
from app.core.db import get_db
from app.models import (
    FEE_STATUSES,
    LiveAttendance,
    Student,
    StudentGrade,
    StudentInvoice,
    Subject,
    User,
)

router = APIRouter(prefix="/api/v1/school", tags=["school-analytics"])

any_school_user = require_school()
manager_only = require_school("school_manager")

#: Score bands used by the performance distribution chart.
SCORE_BANDS = (
    ("0-39", 0, 39.99, "#c0392b"),
    ("40-54", 40, 54.99, "#e08e0b"),
    ("55-69", 55, 69.99, "#2e86de"),
    ("70-84", 70, 84.99, "#27ae60"),
    ("85-100", 85, 100, "#1e8449"),
)


def _band(score: float) -> str:
    for label, low, high, _colour in SCORE_BANDS:
        if low <= score <= high:
            return label
    return "0-39"


@router.get("/analytics/kpis")
def kpis(user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    """Headline cards: enrolment, attendance, performance, fee collection."""
    total_students = (
        db.query(func.count(Student.id))
        .filter_by(school_id=user.school_id, is_active=True)
        .scalar()
    )

    attendance = (
        db.query(
            func.count(LiveAttendance.id),
            func.sum(case((LiveAttendance.status == "Present", 1), else_=0)),
        )
        .filter_by(school_id=user.school_id)
        .one()
    )
    recorded = int(attendance[0] or 0)
    present = int(attendance[1] or 0)

    avg_score = (
        db.query(func.avg(StudentGrade.numeric_score))
        .filter_by(school_id=user.school_id)
        .scalar()
    )

    return {
        "total_students": total_students,
        "attendance": {
            "days_recorded": recorded,
            "attendance_pct": round(present / recorded * 100, 1) if recorded else None,
        },
        "average_score": round(float(avg_score), 1) if avg_score is not None else None,
    }


@router.get("/analytics/tuition-status")
def tuition_status(user: User = Depends(manager_only), db: Session = Depends(get_db)):
    """Tuition Status Breakdown: PAID / PENDING / NOT_PAID / SCHOLARSHIP."""
    rows = (
        db.query(Student.fee_status, func.count(Student.id))
        .filter_by(school_id=user.school_id, is_active=True)
        .group_by(Student.fee_status)
        .all()
    )
    counts = {status: 0 for status in FEE_STATUSES}
    for status, count in rows:
        counts[status or "NOT_PAID"] = counts.get(status or "NOT_PAID", 0) + count
    total = sum(counts.values()) or 1

    invoiced, collected = (
        db.query(
            func.coalesce(func.sum(StudentInvoice.amount_due), 0),
            func.coalesce(func.sum(StudentInvoice.amount_paid), 0),
        )
        .filter_by(school_id=user.school_id)
        .one()
    )
    invoiced_f = float(invoiced or 0)
    collected_f = float(collected or 0)

    by_status_ledger = dict(
        db.query(StudentInvoice.status, func.count(StudentInvoice.id))
        .filter_by(school_id=user.school_id)
        .group_by(StudentInvoice.status)
        .all()
    )

    return {
        "breakdown": [
            {
                "status": status,
                "students": counts[status],
                "share_pct": round(counts[status] / total * 100, 1),
            }
            for status in FEE_STATUSES
        ],
        "total_students": sum(counts.values()),
        "collection_matrix": {
            "invoiced": invoiced_f,
            "collected": collected_f,
            "outstanding": round(invoiced_f - collected_f, 2),
            "collection_rate_pct": round(collected_f / invoiced_f * 100, 1) if invoiced_f else None,
            "invoices_by_status": by_status_ledger,
        },
    }


@router.get("/analytics/performance")
def performance(
    exam_name: str | None = None,
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Grade distribution bands plus per-subject and per-class averages."""
    query = db.query(StudentGrade).filter_by(school_id=user.school_id)
    if exam_name:
        query = query.filter_by(exam_name=exam_name)
    grades = query.all()

    distribution = {label: 0 for label, *_ in SCORE_BANDS}
    for grade in grades:
        distribution[_band(float(grade.numeric_score))] += 1

    subject_rows = (
        db.query(
            Subject.subject_name,
            func.avg(StudentGrade.numeric_score),
            func.count(StudentGrade.id),
        )
        .join(StudentGrade, StudentGrade.subject_id == Subject.id)
        .filter(StudentGrade.school_id == user.school_id)
        .group_by(Subject.subject_name)
        .order_by(Subject.subject_name)
        .all()
    )

    by_class: dict[int, list[float]] = {}
    for grade in grades:
        by_class.setdefault(grade.class_id, []).append(float(grade.numeric_score))

    return {
        "exams_considered": sorted({g.exam_name for g in grades}),
        "records": len(grades),
        "distribution": [
            {
                "band": label,
                "students": distribution[label],
                "colour": colour,
                "share_pct": round(distribution[label] / len(grades) * 100, 1) if grades else 0,
            }
            for label, _low, _high, colour in SCORE_BANDS
        ],
        "by_subject": [
            {"subject": name, "average_score": round(float(avg), 1), "entries": count}
            for name, avg, count in subject_rows
        ],
        "by_class": [
            {"class_id": class_id, "average_score": round(sum(v) / len(v), 1)}
            for class_id, v in sorted(by_class.items())
        ],
    }


@router.get("/analytics/attendance-trend")
def attendance_trend(
    days: int = Query(default=14, ge=1, le=90),
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    """Daily attendance percentage trend across the recent window."""
    cutoff = dt.date.today() - dt.timedelta(days=days)

    rows = (
        db.query(
            LiveAttendance.date,
            func.count(LiveAttendance.id),
            func.sum(case((LiveAttendance.status == "Present", 1), else_=0)),
            func.sum(case((LiveAttendance.status == "Absent", 1), else_=0)),
        )
        .filter(
            LiveAttendance.school_id == user.school_id,
            LiveAttendance.date >= cutoff,
        )
        .group_by(LiveAttendance.date)
        .order_by(LiveAttendance.date)
        .all()
    )

    trend = []
    for day, total, present, absent in rows:
        total_i = int(total or 0)
        present_i = int(present or 0)
        trend.append(
            {
                "date": day.isoformat(),
                "total": total_i,
                "present": present_i,
                "absent": int(absent or 0),
                "attendance_pct": round(present_i / total_i * 100, 1) if total_i else None,
            }
        )

    recorded = [t["attendance_pct"] for t in trend if t["attendance_pct"] is not None]
    return {
        "days": days,
        "trend": trend,
        "average_pct": round(sum(recorded) / len(recorded), 1) if recorded else None,
    }

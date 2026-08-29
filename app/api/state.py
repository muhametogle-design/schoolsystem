"""STATE GOVERNMENT SUPER-ADMIN PORTAL (read-only academics + alarm engine).

Every route requires the state_inspector role. Financial data is
structurally absent from this router: there is no route, no service import
and no query that can express it.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_state
from app.core.db import get_db
from app.models import CommunicationLog, ExamSubmissionEvent, PrivateSchool, User
from app.services.analytics import (
    state_live_attendance_feed,
    view_a_state_compliance_map,
    view_b_student_lookup,
    view_c_grade_analytics,
)
from app.services.compliance import process_daily_attendance_deadlines

router = APIRouter(prefix="/api/v1/state", tags=["state-portal"], dependencies=[Depends(require_state)])


@router.get("/compliance-map")
def compliance_map(db: Session = Depends(get_db)):
    """View A — State Supervisor Core Command Map & Alarm Portal."""
    rows = view_a_state_compliance_map(db)
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "attendance_deadline": "12:00",
        "alarm_audit_time": "15:00",
        "summary": {
            "active_schools": len(rows),
            "red_alarms": sum(1 for r in rows if r["is_red_alarm_active"]),
            "compliant": sum(1 for r in rows if r["daily_attendance_logged"]),
            "pending": sum(1 for r in rows if not r["daily_attendance_logged"]),
        },
        "schools": rows,
    }


@router.get("/students/search")
def student_lookup(q: str = Query(min_length=1), db: Session = Depends(get_db)):
    """View B — State-Wide Student ID National Lookup Engine."""
    return {"query": q, "results": view_b_student_lookup(db, q)}


@router.get("/analytics/grades")
def grade_analytics(
    school_id: int | None = None,
    class_level: str | None = Query(default=None, description="e.g. 'Class 7'"),
    db: Session = Depends(get_db),
):
    """Query C — State Subject Benchmarking Index (release-token filtered)."""
    return {
        "filtered_to": "exam_submission_events",
        "filtered_to_published_exams": True,
        "rows": view_c_grade_analytics(db, school_id=school_id, class_level=class_level),
    }


@router.get("/attendance/live")
def live_attendance(
    school_id: int | None = None,
    class_level: str | None = Query(default=None, description="e.g. 'Class 7' — Class 1 to 12 filter"),
    date: dt.date | None = None,
    db: Session = Depends(get_db),
):
    """Read-only state visibility into live attendance logs."""
    return {
        "date": (date or dt.date.today()).isoformat(),
        "filtered_class_level": class_level,
        "records": state_live_attendance_feed(
            db, school_id=school_id, target_date=date, class_level=class_level
        ),
    }


@router.get("/alarms")
def alarm_feed(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(CommunicationLog)
            .where(CommunicationLog.message_type == "Red_Alarm")
            .order_by(CommunicationLog.timestamp_sent.desc())
            .limit(min(limit, 200))
        )
        .scalars()
        .all()
    )
    return {
        "alarms": [
            {
                "id": a.id,
                "school_id": a.school_id,
                "message": a.message_content,
                "delivery_status": a.delivery_status,
                "timestamp_sent": a.timestamp_sent.isoformat() if a.timestamp_sent else None,
            }
            for a in rows
        ]
    }


@router.get("/exam-events")
def exam_events(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(ExamSubmissionEvent).order_by(ExamSubmissionEvent.published_at.desc()).limit(min(limit, 200))
        )
        .scalars()
        .all()
    )
    return {
        "events": [
            {
                "id": e.id,
                "school_id": e.school_id,
                "class_id": e.class_id,
                "subject_id": e.subject_id,
                "exam_name": e.exam_name,
                "records_released": e.records_released,
                "published_by": e.published_by,
                "published_at": e.published_at.isoformat() if e.published_at else None,
            }
            for e in rows
        ]
    }


@router.get("/schools")
def schools_list(db: Session = Depends(get_db)):
    rows = db.execute(select(PrivateSchool).order_by(PrivateSchool.school_name)).scalars().all()
    return {
        "schools": [
            {
                "id": s.id,
                "school_name": s.school_name,
                "state_license_number": s.state_license_number,
                "accreditation_status": s.accreditation_status,
                "contact_phone": s.contact_phone,
            }
            for s in rows
        ]
    }


@router.post("/audit/run")
def run_red_alarm_audit(
    db: Session = Depends(get_db),
    user: User = Depends(require_state),
):
    """Manually trigger the Phase 2 15:00 worker (normally cron-driven)."""
    raised = process_daily_attendance_deadlines(db)
    return {"ran_by": user.email, "ran_at": dt.datetime.now(dt.timezone.utc).isoformat(), "red_alarms_raised": len(raised), "alarms": raised}

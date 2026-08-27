"""Phase 1 Data Ingestion API.

School clerks submit daily attendance, midterm grades, hires and payroll
hours. Every batch is validated with real-time format rules before it is
persisted; rejected rows are returned so clerks can correct them.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import campus_context, get_principal, get_session
from app.core.tenancy import Principal
from app.schemas.academics import AttendanceCreate, GradeCreate, ValidatePayload
from app.services.ingestion import (
    IngestionError,
    ValidationResult,
    persist_attendance,
    persist_grades,
    persist_payroll,
    persist_teachers,
    validate_batch,
)

router = APIRouter(prefix="/ingestion", tags=["phase-1-ingestion"])


@router.post("/validate")
def validate_payload(
    body: ValidatePayload,
    campus_id: uuid.UUID = Depends(campus_context),
    session: Session = Depends(get_session),
):
    """Real-time format validation without writing anything."""
    results, accepted = validate_batch(body.record_type, body.records)
    return {
        "record_type": body.record_type,
        "total": len(body.records),
        "accepted": accepted,
        "rejected": len(body.records) - accepted,
        "rows": [
            {
                "row_id": r.row_id,
                "passed": r.passed,
                "errors": r.errors,
                "rules": r.rules,
            }
            for r in results
        ],
    }


@router.post("")
def submit(
    body: ValidatePayload,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    """Validate then persist a sealed Phase-1 batch."""
    if principal.role not in ("clerk", "dean"):
        raise HTTPException(403, "Only clerks or deans may ingest data")

    try:
        results, accepted = validate_batch(body.record_type, body.records)
    except IngestionError as exc:
        raise HTTPException(422, str(exc))

    if accepted == 0:
        return {
            "status": "rejected",
            "accepted": 0,
            "rejected": len(body.records),
            "message": "No records passed validation",
        }

    valid_rows = [r for r in results if r.passed]
    # Map results back to the original row dicts by row_id.
    by_id = {r.row_id: body.records[r.row_id - 1] for r in valid_rows}
    rows = [by_id[r.row_id] for r in valid_rows]

    # Persist only validated rows for the clerk's campus.
    if body.record_type == "attendance":
        count = persist_attendance(session, campus_id=campus_id, clerk_id=principal.user_id, rows=rows)
    elif body.record_type == "grade":
        count = persist_grades(session, campus_id=campus_id, clerk_id=principal.user_id, rows=rows)
    elif body.record_type == "teacher":
        count = persist_teachers(session, campus_id=campus_id, clerk_id=principal.user_id, rows=rows)
    elif body.record_type == "payroll":
        count = persist_payroll(session, campus_id=campus_id, clerk_id=principal.user_id, rows=rows)
    else:
        raise HTTPException(422, f"Unsupported record_type {body.record_type}")

    session.flush()
    return {
        "status": "accepted",
        "accepted": count,
        "rejected": len(body.records) - count,
        "message": f"{count} {body.record_type} record(s) ingested for campus {campus_id}",
    }


@router.post("/attendance", status_code=201)
def submit_attendance(
    body: AttendanceCreate,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("clerk", "dean"):
        raise HTTPException(403, "Only clerks or deans may submit attendance")
    session.execute(
        text(
            "INSERT INTO attendance (student_id, course_section_id, campus_id, "
            "attendance_date, status, hours, clerk_id, source) VALUES "
            "(:sid, :csid, :cid, :d, :st, :h, :clerk, 'portal')"
        ),
        {
            "sid": str(body.student_id),
            "csid": str(body.course_section_id) if body.course_section_id else None,
            "cid": str(campus_id),
            "d": body.attendance_date,
            "st": body.status,
            "h": body.hours,
            "clerk": str(principal.user_id),
        },
    )
    return {"status": "accepted", "student_id": str(body.student_id), "date": str(body.attendance_date)}


@router.post("/grades", status_code=201)
def submit_grade(
    body: GradeCreate,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("clerk", "dean"):
        raise HTTPException(403, "Only clerks or deans may submit grades")
    sheet = session.execute(
        text(
            "INSERT INTO exam_sheets (course_section_id, student_id, campus_id, "
            "exam_type, score, recorded_by) VALUES (:cs, :sid, :cid, :et, :sc, :clerk) "
            "ON CONFLICT (course_section_id, student_id, exam_type) "
            "DO UPDATE SET score = EXCLUDED.score RETURNING id"
        ),
        {
            "cs": str(body.course_section_id),
            "sid": str(body.student_id),
            "cid": str(campus_id),
            "et": body.exam_type,
            "sc": body.score,
            "clerk": str(principal.user_id),
        },
    ).scalar()
    return {"id": str(sheet), "status": "accepted"}

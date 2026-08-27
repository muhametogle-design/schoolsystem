"""Phase 3 Overnight Aggregation API.

Triggers the night job (system/aggregator roles), reports batch status, and
lets state admins inspect the central registries.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_principal, get_session
from app.core.config import settings
from app.core.tenancy import Principal
from app.models.audit import AggregationBatch, CentralStudentRegistry, CentralTeacherRegistry
from app.services.aggregation import run_overnight_batch

router = APIRouter(prefix="/aggregation", tags=["phase-3-aggregation"])


class RunBatchRequest(BaseModel):
    batch_date: date


@router.post("/run")
def run_batch(
    body: RunBatchRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("system", "aggregator", "state_admin"):
        raise HTTPException(403, "Only aggregation/system roles may run the overnight batch")
    try:
        stats = run_overnight_batch(
            session, batch_date=body.batch_date, limit=settings.aggregation_batch_limit
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Batch failed: {exc}")
    return {"status": "completed", "stats": stats}


@router.get("/batches")
def list_batches(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("system", "aggregator", "state_admin"):
        raise HTTPException(403, "Only state/system roles may view batches")
    rows = session.scalars(
        select(AggregationBatch).order_by(AggregationBatch.created_at.desc()).limit(100)
    ).all()
    return [
        {
            "id": str(r.id),
            "batch_date": r.batch_date.isoformat(),
            "phase": r.phase,
            "batch_state": r.batch_state,
            "stats": r.stats,
            "error": r.error,
        }
        for r in rows
    ]


@router.get("/student-registry")
def student_registry(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("system", "aggregator", "state_admin"):
        raise HTTPException(403, "Only state/system roles may read the central registry")
    rows = session.scalars(
        select(CentralStudentRegistry).order_by(CentralStudentRegistry.aggregated_at.desc()).limit(200)
    ).all()
    return [
        {
            "ne_sid": r.ne_sid,
            "current_campus_id": str(r.current_campus_id),
            "schooling_history": r.schooling_history,
            "gpa_trend": r.gpa_trend,
            "snapshot_key": r.snapshot_key,
        }
        for r in rows
    ]


@router.get("/teacher-registry")
def teacher_registry(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("system", "aggregator", "state_admin"):
        raise HTTPException(403, "Only state/system roles may read the central registry")
    rows = session.scalars(
        select(CentralTeacherRegistry).order_by(CentralTeacherRegistry.aggregated_at.desc()).limit(200)
    ).all()
    return [
        {
            "ne_tid": r.ne_tid,
            "current_campus_id": str(r.current_campus_id),
            "qualifications": r.qualifications,
            "certifications": r.certifications,
            "payroll_profile": r.payroll_profile,
            "status": r.status,
        }
        for r in rows
    ]

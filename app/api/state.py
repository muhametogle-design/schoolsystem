"""Phase 4 State Control Services API.

State admins analyze KPIs, trigger automated funding payouts and reallocate
teaching staff. These endpoints are read-dominant and always require a
state-level role.

NOTES ON RLS: *After* a campus credential has switched to state-admin the
state tables (``central.*``) are visible because they are not tenant tables;
state operations that need to write into a campus table still use the
``sys_campus_role`` session setter in deployment via the ``app.portal``
service (see ``app/services/portal.py`` reference).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_principal, get_session
from app.core.tenancy import Principal
from app.models.audit import CentralFundingPayout, CentralKpiRollup
from app.models.teachers import CivilServiceGrade, TeacherPayrollProfile
from app.services.state_control import (
    approve_payout,
    compute_capitation_payouts,
    compute_kpi_rollup,
    compute_payroll_payouts,
    list_teacher_vacancies,
    settle_payout,
)

router = APIRouter(prefix="/state", tags=["phase-4-state-control"])

STATE_ONLY = ("state_admin", "system")


def _guard(principal: Principal) -> None:
    if principal.role not in STATE_ONLY:
        raise HTTPException(403, "State admin role required")


@router.get("/kpis")
def get_kpis(
    state_code: str,
    period_start: date,
    period_end: date,
    campus_id: uuid.UUID | None = None,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    _guard(principal)
    rollup = compute_kpi_rollup(
        session,
        state_code=state_code,
        period_start=period_start,
        period_end=period_end,
        campus_id=campus_id,
    )
    return {
        "state_code": state_code,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "metrics": rollup.metrics,
    }


class VacancyQuery(BaseModel):
    state_code: str
    academic_year_id: uuid.UUID
    term_id: uuid.UUID


@router.post("/vacancies")
def vacancies(
    body: VacancyQuery,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    _guard(principal)
    return list_teacher_vacancies(
        session,
        state_code=body.state_code,
        academic_year_id=body.academic_year_id,
        term_id=body.term_id,
    )


class PayrollFundingRequest(BaseModel):
    period: str
    campus_id: uuid.UUID | None = None


@router.post("/payouts/payroll")
def generate_payroll_payouts(
    body: PayrollFundingRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    _guard(principal)
    # Phase-4 trigger: only pay-out entries that deans have approved in Phase 2.
    rows = compute_payroll_payouts(session, period=body.period, campus_id=body.campus_id)
    return [
        {"payout_id": str(r.id), "campus_id": str(r.campus_id), "amount": str(r.amount), "status": r.status}
        for r in rows
    ]


class CapitationFundingRequest(BaseModel):
    period: str
    per_student_rate: float
    campus_id: uuid.UUID | None = None


@router.post("/payouts/capitation")
def generate_capitation_payouts(
    body: CapitationFundingRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    _guard(principal)
    rows = compute_capitation_payouts(
        session,
        period=body.period,
        per_student_rate=body.per_student_rate,
        campus_id=body.campus_id,
    )
    return [
        {"payout_id": str(r.id), "campus_id": str(r.campus_id), "amount": str(r.amount), "status": r.status}
        for r in rows
    ]


@router.post("/payouts/{payout_id}/approve")
def approve(
    payout_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    _guard(principal)
    row = approve_payout(session, payout_id=payout_id, approved_by=principal.manager_id or principal.user_id)
    return {"payout_id": str(row.id), "status": row.status, "approved_at": row.approved_at.isoformat()}


class SettleRequest(BaseModel):
    ledger_ref: str


@router.post("/payouts/{payout_id}/settle")
def settle(
    payout_id: uuid.UUID,
    body: SettleRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    _guard(principal)
    row = settle_payout(session, payout_id=payout_id, ledger_ref=body.ledger_ref)
    return {"payout_id": str(row.id), "status": row.status, "paid_at": row.paid_at.isoformat()}


@router.get("/payroll-tiers")
def list_tiers(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    _guard(principal)
    tiers = session.scalars(select(CivilServiceGrade).order_by(CivilServiceGrade.grade_tier)).all()
    return [
        {
            "grade_tier": t.grade_tier,
            "base_salary_naira": str(t.base_salary_naira),
            "hardship_multiplier": str(t.hardship_multiplier),
        }
        for t in tiers
    ]

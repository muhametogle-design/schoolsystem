"""Teacher & Payroll Governance endpoints."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import campus_context, get_principal, get_session
from app.core.tenancy import Principal
from app.models.teachers import (
    CivilServiceGrade,
    PayrollEntry,
    Teacher,
    TeacherBackgroundLog,
    TeacherCertification,
    TeacherExitRecord,
    TeacherPayrollProfile,
)
from app.schemas.teachers import (
    PayrollEntryCreate,
    PayrollProfileCreate,
    TeacherCertificationCreate,
    TeacherCreate,
    TeacherOut,
)

router = APIRouter(prefix="/teachers", tags=["teacher-governance"])


@router.post("", response_model=TeacherOut, status_code=201)
def create_teacher(
    body: TeacherCreate,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("clerk", "dean"):
        raise HTTPException(403, "Only clerks or deans may register teachers")
    teacher = Teacher(
        campus_id=campus_id,
        first_name=body.first_name,
        last_name=body.last_name,
        dob=body.dob,
        is_civil_service=body.is_civil_service,
        hire_date=body.hire_date or date.today(),
        employment_state="active",
    )
    session.add(teacher)
    session.flush()
    session.refresh(teacher)  # fetch NE-TID set by DB trigger
    return teacher


@router.get("", response_model=list[TeacherOut])
def list_teachers(
    campus_id: uuid.UUID = Depends(campus_context),
    session: Session = Depends(get_session),
):
    return session.scalars(
        select(Teacher).where(Teacher.campus_id == campus_id).order_by(Teacher.last_name)
    ).all()


@router.get("/{teacher_id}", response_model=TeacherOut)
def get_teacher(
    teacher_id: uuid.UUID,
    campus_id: uuid.UUID = Depends(campus_context),
    session: Session = Depends(get_session),
):
    row = session.scalar(
        select(Teacher).where(Teacher.id == teacher_id, Teacher.campus_id == campus_id)
    )
    if row is None:
        raise HTTPException(404, "Teacher not found in this campus")
    return row


@router.post("/{teacher_id}/certifications", status_code=201)
def add_certification(
    teacher_id: uuid.UUID,
    body: TeacherCertificationCreate,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("clerk", "dean"):
        raise HTTPException(403, "Only clerks or deans may add certifications")
    cert = TeacherCertification(
        teacher_id=teacher_id,
        campus_id=campus_id,
        cert_kind=body.cert_kind,
        cert_no=body.cert_no,
        issue_date=body.issue_date,
        expiry_date=body.expiry_date,
        next_renewal=body.next_renewal,
        status="active",
    )
    session.add(cert)
    session.flush()
    return {"id": str(cert.id), "cert_kind": cert.cert_kind, "status": cert.status}


@router.post("/{teacher_id}/payroll-profile", status_code=201)
def upsert_payroll_profile(
    teacher_id: uuid.UUID,
    body: PayrollProfileCreate,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("clerk", "dean"):
        raise HTTPException(403, "Only clerks or deans may manage payroll profiles")
    grade = session.scalar(
        select(CivilServiceGrade).where(
            CivilServiceGrade.grade_tier == body.grade_tier,
            CivilServiceGrade.is_active.is_(True),
        )
    )
    if grade is None:
        raise HTTPException(422, "Invalid civil service grade tier")
    profile = session.scalar(
        select(TeacherPayrollProfile).where(TeacherPayrollProfile.teacher_id == teacher_id)
    )
    if profile is None:
        profile = TeacherPayrollProfile(
            teacher_id=teacher_id, campus_id=campus_id, tin=body.tin
        )
        session.add(profile)
    profile.grade_tier = body.grade_tier
    profile.hardship_zone = body.hardship_zone
    profile.regional_allowance = body.regional_allowance
    profile.bank_code = body.bank_code
    profile.pension_rate = body.pension_rate
    profile.is_tin_verified = False
    session.flush()
    return {"teacher_id": str(teacher_id), "grade_tier": profile.grade_tier, "tin_masked": body.tin[:2] + "***"}


@router.get("/{teacher_id}/background-log", response_model=list[dict])
def background_log(
    teacher_id: uuid.UUID,
    campus_id: uuid.UUID = Depends(campus_context),
    session: Session = Depends(get_session),
):
    rows = session.scalars(
        select(TeacherBackgroundLog)
        .where(
            TeacherBackgroundLog.teacher_id == teacher_id,
            TeacherBackgroundLog.campus_id == campus_id,
        )
        .order_by(TeacherBackgroundLog.occurred_at.desc())
    ).all()
    return [
        {
            "id": str(r.id),
            "event_type": r.event_type,
            "description": r.description,
            "occurred_at": r.occurred_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/{teacher_id}/exit", status_code=201)
def record_exit(
    teacher_id: uuid.UUID,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.manager_id is None:
        raise HTTPException(403, "Exit record requires manager signature")
    teacher = session.scalar(
        select(Teacher).where(Teacher.id == teacher_id, Teacher.campus_id == campus_id)
    )
    if teacher is None:
        raise HTTPException(404, "Teacher not found")
    exit_rec = TeacherExitRecord(
        teacher_id=teacher_id,
        campus_id=campus_id,
        exit_date=date.today(),
        reason="administrative",
        signed_by=principal.manager_id,
    )
    teacher.employment_state = "transferred"
    session.add(exit_rec)
    session.flush()
    return {"teacher_id": str(teacher_id), "state": teacher.employment_state}


@router.post("/payroll", status_code=201)
def submit_payroll(
    body: PayrollEntryCreate,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("clerk", "dean"):
        raise HTTPException(403, "Only clerks or deans may submit payroll hours")
    existing = session.scalar(
        select(PayrollEntry).where(
            PayrollEntry.teacher_id == body.teacher_id,
            PayrollEntry.pay_period == body.pay_period,
        )
    )
    if existing is not None:
        raise HTTPException(409, "Payroll entry already exists for that period")
    entry = PayrollEntry(
        teacher_id=body.teacher_id,
        campus_id=campus_id,
        pay_period=body.pay_period,
        hours=body.hours,
        base_pay=body.base_pay,
        hardship_allowance=body.hardship_allowance,
        gross=body.gross,
        pension_deduction=body.pension_deduction,
        net=body.net,
        submitted_by=principal.user_id,
        status="pending",
    )
    session.add(entry)
    session.flush()
    return {"id": str(entry.id), "pay_period": entry.pay_period, "status": entry.status}

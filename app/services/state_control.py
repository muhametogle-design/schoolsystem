"""Phase 4 State Control Services.

Query services for:
  * regional KPI metrics (enrolment, attendance, truancy, vacancy)
  * teacher vacancy tracking
  * automated payroll payouts and funding disbursements (formula driven)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.academics import Attendance, Transcript
from app.models.audit import CentralFundingPayout, CentralKpiRollup
from app.models.registry import Enrollment, Student, StudentMobility
from app.models.teachers import PayrollEntry, Teacher, TeacherAssignment
from app.models.identity import Campus

TRUANCY_ABSENCE_THRESHOLD = 10


def compute_kpi_rollup(
    session: Session,
    *,
    state_code: str,
    period_start: date,
    period_end: date,
    campus_id: Optional[uuid.UUID] = None,
) -> CentralKpiRollup:
    """Compute enrolments + attendance + truancy + staffing KPI per campus."""

    base = (
        select(Campus)
        .where(Campus.state_code == state_code, Campus.is_active.is_(True))
    )
    if campus_id:
        base = base.where(Campus.id == campus_id)
    campuses = session.scalars(base).all()

    metrics: List[Dict[str, Any]] = []
    for campus in campuses:
        student_count = session.scalar(
            select(func.count(Student.id)).where(
                Student.campus_id == campus.id, Student.status == "active"
            )
        ) or 0

        teacher_count = session.scalar(
            select(func.count(Teacher.id)).where(
                Teacher.campus_id == campus.id, Teacher.employment_state == "active"
            )
        ) or 0

        attendance_rows = session.execute(
            select(Attendance.status, func.count(Attendance.id))
            .where(
                Attendance.campus_id == campus.id,
                Attendance.attendance_date.between(period_start, period_end),
            )
            .group_by(Attendance.status)
        ).all()
        attendance_by_status = {s: c for s, c in attendance_rows}
        total_attendance = sum(attendance_by_status.values()) or 1

        truant_students = session.scalar(
            select(func.count(func.distinct(Attendance.student_id))).where(
                Attendance.campus_id == campus.id,
                Attendance.status == "truant",
                Attendance.attendance_date.between(period_start, period_end),
            )
        ) or 0

        open_vacancies = session.scalar(
            select(func.count(TeacherAssignment.id)).where(
                TeacherAssignment.campus_id == campus.id
            )
        ) or 0

        metrics.append(
            {
                "campus_id": str(campus.id),
                "campus_code": campus.campus_code,
                "state_code": campus.state_code,
                "enrolled_students": student_count,
                "active_teachers": teacher_count,
                "student_teacher_ratio": round(student_count / max(teacher_count, 1), 2),
                "attendance_rate_pct": round(
                    (attendance_by_status.get("present", 0) / total_attendance) * 100, 2
                ),
                "truant_students": truant_students,
                "chronic_truancy_rate_pct": round(
                    (truant_students / max(student_count, 1)) * 100, 2
                ),
                "open_vacancies": open_vacancies,
            }
        )

    return CentralKpiRollup(
        state_code=state_code,
        campus_id=campus_id,
        period_start=period_start,
        period_end=period_end,
        metrics={"campuses": metrics},
        computed_at=datetime.now(timezone.utc),
    )


def list_teacher_vacancies(
    session: Session,
    *,
    state_code: str,
    academic_year_id: uuid.UUID,
    term_id: uuid.UUID,
) -> List[Dict[str, Any]]:
    """Report sections with no active lead teacher (Phase 4 reallocation view)."""

    campuses = session.scalars(
        select(Campus).where(Campus.state_code == state_code, Campus.is_active.is_(True))
    ).all()
    result: List[Dict[str, Any]] = []

    # Simplified raw query for reference read-model; real deployments join
    # course_sections with teacher_assignments.
    for campus in campuses:
        sections = session.execute(
            select(
                func.count(TeacherAssignment.id),
            )
            .join(Campus, Campus.id == TeacherAssignment.campus_id)
            .where(
                Campus.id == campus.id,
                TeacherAssignment.role == "lead",
            )
        ).scalar() or 0
        count_sections = session.execute(
            select(func.count(TeacherAssignment.id)).where(
                TeacherAssignment.campus_id == campus.id
            )
        ).scalar() or 0
        result.append(
            {
                "campus_id": str(campus.id),
                "campus_code": campus.campus_code,
                "campus_type": campus.campus_type,
                "lead_assigned_sections": sections,
                "total_assigned_sections": count_sections,
                "assigned_vacancies": max(count_sections - sections, 0),
                "state_code": campus.state_code,
            }
        )
    return result


def compute_payroll_payouts(
    session: Session,
    *,
    period: str,
    campus_id: Optional[uuid.UUID] = None,
) -> List[CentralFundingPayout]:
    """Translate approved payroll entries into central funding payout rows."""
    query = (
        select(PayrollEntry)
        .where(PayrollEntry.pay_period == period, PayrollEntry.status == "approved")
        .order_by(PayrollEntry.campus_id)
    )
    if campus_id:
        query = query.where(PayrollEntry.campus_id == campus_id)
    entries = session.scalars(query).all()

    by_campus: Dict[uuid.UUID, Dict[str, float]] = {}
    for e in entries:
        agg = by_campus.setdefault(
            e.campus_id,
            {"gross": 0.0, "net": 0.0, "pension": 0.0, "count": 0.0},
        )
        agg["gross"] += float(e.gross)
        agg["net"] += float(e.net)
        agg["pension"] += float(e.pension_deduction)
        agg["count"] += 1

    payouts: List[CentralFundingPayout] = []
    for campus, agg in by_campus.items():
        row = session.scalar(
            select(CentralFundingPayout).where(
                CentralFundingPayout.campus_id == campus,
                CentralFundingPayout.period == period,
                CentralFundingPayout.funding_kind == "teacher_payroll",
            )
        )
        formula = {
            "period": period,
            "teachers": agg["count"],
            "net_payroll": agg["net"],
            "pension_remitted": agg["pension"],
            "basis": "approved_payroll_entries",
        }
        amount = round(agg["net"], 2)
        if row is None:
            row = CentralFundingPayout(
                campus_id=campus,
                period=period,
                funding_kind="teacher_payroll",
                formula=formula,
                amount=amount,
                status="pending",
            )
            session.add(row)
        else:
            row.formula = formula
            row.amount = amount
        payouts.append(row)
    session.flush()
    return payouts


def compute_capitation_payouts(
    session: Session,
    *,
    period: str,
    per_student_rate: float,
    campus_id: Optional[uuid.UUID] = None,
) -> List[CentralFundingPayout]:
    """Automated per-capita funding payout based on active enrolments."""
    campuses = session.scalars(
        select(Campus).where(Campus.is_active.is_(True))
    ).all()
    payouts: List[CentralFundingPayout] = []
    for campus in campuses:
        if campus_id and campus.id != campus_id:
            continue
        students = session.scalar(
            select(func.count(Enrollment.id))
            .where(Enrollment.campus_id == campus.id, Enrollment.status == "active")
        ) or 0
        amount = round(students * per_student_rate, 2)
        row = session.scalar(
            select(CentralFundingPayout).where(
                CentralFundingPayout.campus_id == campus.id,
                CentralFundingPayout.period == period,
                CentralFundingPayout.funding_kind == "capitation",
            )
        )
        formula = {
            "period": period,
            "active_students": students,
            "per_student_rate": per_student_rate,
        }
        if row is None:
            row = CentralFundingPayout(
                campus_id=campus.id,
                period=period,
                funding_kind="capitation",
                formula=formula,
                amount=amount,
                status="pending",
            )
            session.add(row)
        else:
            row.formula = formula
            row.amount = amount
        payouts.append(row)
    session.flush()
    return payouts


def approve_payout(
    session: Session,
    *,
    payout_id: uuid.UUID,
    approved_by: uuid.UUID,
) -> CentralFundingPayout:
    row = session.get(CentralFundingPayout, payout_id)
    if row is None:
        raise ValueError("Payout not found")
    row.status = "approved"
    row.approved_by = approved_by
    row.approved_at = datetime.now(timezone.utc)
    session.flush()
    return row


def settle_payout(
    session: Session,
    *,
    payout_id: uuid.UUID,
    ledger_ref: str,
) -> CentralFundingPayout:
    row = session.get(CentralFundingPayout, payout_id)
    if row is None:
        raise ValueError("Payout not found")
    if row.status != "approved":
        raise ValueError("Payout must be approved before settlement")
    row.status = "paid"
    row.paid_at = datetime.now(timezone.utc)
    row.ledger_ref = ledger_ref
    session.flush()
    return row

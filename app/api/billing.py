"""🔒 PRIVATE FINANCIAL ERP — `/api/v1/school/finance/` 🔒

Base tuition rates, billing configurations, student ledgers, outstanding
balances, revenue summaries and transaction payment logs.

HARD SECURITY RULE: this path group is guarded by
`require_school('school_manager')`. A token representing a 'state_inspector'
that attempts any financial reporting endpoint here is immediately aborted
with HTTP 403 Forbidden — and the attempt is recorded in security_audit_log.
On PostgreSQL the state_readonly role additionally holds zero grants on the
financial tables, which carry explicit DENY-ALL RLS policies.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_school
from app.core.db import get_db
from app.models import (
    PaymentTransaction,
    Student,
    StudentInvoice,
    TuitionRate,
    User,
)
from app.schemas import (
    InvoiceCreate,
    InvoiceUpdate,
    PaymentCreate,
    PaymentUpdate,
    TuitionRateCreate,
    TuitionRateUpdate,
)

router = APIRouter(prefix="/api/v1/school/finance", tags=["finance-private 🔒"])

manager_only = require_school("school_manager")


@router.get("/summary")
def billing_summary(user: User = Depends(manager_only), db: Session = Depends(get_db)):
    invoices = (
        db.query(StudentInvoice)
        .options(joinedload(StudentInvoice.student))
        .filter_by(school_id=user.school_id)
        .all()
    )
    total_due = sum(float(i.amount_due) for i in invoices)
    total_paid = sum(float(i.amount_paid) for i in invoices)
    outstanding = total_due - total_paid
    return {
        "school_id": user.school_id,
        "visibility": "PRIVATE — firewalled from all State Government roles",
        "total_billed": round(total_due, 2),
        "total_collected": round(total_paid, 2),
        "outstanding_balance": round(outstanding, 2),
        "invoice_counts": {
            "all": len(invoices),
            "settled": sum(1 for i in invoices if i.status in ("PAID", "Settled")),
            "partially_paid": sum(1 for i in invoices if i.status in ("PENDING", "Partially_Paid")),
            "outstanding": sum(1 for i in invoices if i.status in ("NOT_PAID", "Outstanding")),
            "overdue": sum(1 for i in invoices if i.status == "Overdue"),
        },
    }


@router.get("/tuition-rates")
def list_rates(user: User = Depends(manager_only), db: Session = Depends(get_db)):
    rows = db.query(TuitionRate).filter_by(school_id=user.school_id).order_by(TuitionRate.class_level).all()
    return {
        "tuition_rates": [
            {
                "id": r.id,
                "class_level": r.class_level,
                "base_tuition_amount": float(r.base_tuition_amount),
                "billing_cycle": r.billing_cycle,
            }
            for r in rows
        ]
    }


@router.post("/tuition-rates", status_code=201)
def create_rate(payload: TuitionRateCreate, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    rate = TuitionRate(
        school_id=user.school_id,
        class_level=payload.class_level,
        base_tuition_amount=payload.base_tuition_amount,
        billing_cycle=payload.billing_cycle,
        effective_date=dt.date.today(),
    )
    db.add(rate)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "A rate for this class level + cycle already exists")
    return {"id": rate.id}


def _rate_or_404(db: Session, school_id: int, rate_id: int) -> TuitionRate:
    rate = db.query(TuitionRate).filter_by(id=rate_id, school_id=school_id).one_or_none()
    if not rate:
        raise HTTPException(404, "Tuition rate not found in this school")
    return rate


@router.patch("/tuition-rates/{rate_id}")
def update_rate(
    rate_id: int,
    payload: TuitionRateUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """Edit a tenant's private tuition configuration."""
    rate = _rate_or_404(db, user.school_id, rate_id)
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(rate, field, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "A rate for this class level + cycle already exists")
    return {
        "id": rate.id,
        "class_level": rate.class_level,
        "base_tuition_amount": float(rate.base_tuition_amount),
        "billing_cycle": rate.billing_cycle,
    }


@router.delete("/tuition-rates/{rate_id}")
def delete_rate(rate_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    rate = _rate_or_404(db, user.school_id, rate_id)
    db.delete(rate)
    db.commit()
    return {"deleted": True, "rate_id": rate_id}


@router.get("/invoices")
def list_invoices(
    status_filter: str | None = None, user: User = Depends(manager_only), db: Session = Depends(get_db)
):
    query = (
        db.query(StudentInvoice)
        .options(joinedload(StudentInvoice.student), joinedload(StudentInvoice.payments))
        .filter_by(school_id=user.school_id)
    )
    if status_filter:
        query = query.filter_by(status=status_filter)
    rows = query.order_by(StudentInvoice.created_at.desc()).limit(300).all()
    return {
        "invoices": [
            {
                "id": i.id,
                "student_id": i.student_id,
                "student": f"{i.student.first_name} {i.student.last_name}" if i.student else None,
                "description": i.description,
                "amount_due": float(i.amount_due),
                "amount_paid": float(i.amount_paid),
                "balance": round(float(i.amount_due) - float(i.amount_paid), 2),
                "due_date": i.due_date.isoformat() if i.due_date else None,
                "status": i.status,
                "payments": [
                    {"id": p.id, "amount": float(p.amount), "method": p.payment_method, "paid_at": p.paid_at.isoformat() if p.paid_at else None}
                    for p in i.payments
                ],
            }
            for i in rows
        ]
    }


@router.post("/invoices", status_code=201)
def create_invoice(payload: InvoiceCreate, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    student = (
        db.query(Student).filter_by(id=payload.student_id, school_id=user.school_id).one_or_none()
    )
    if not student:
        raise HTTPException(404, "Student not found in this school")
    invoice = StudentInvoice(
        school_id=user.school_id,
        student_id=payload.student_id,
        description=payload.description,
        amount_due=payload.amount_due,
        due_date=payload.due_date,
        status="NOT_PAID",
    )
    db.add(invoice)
    db.commit()
    return {"id": invoice.id, "status": invoice.status}


def _invoice_or_404(db: Session, school_id: int, invoice_id: int) -> StudentInvoice:
    invoice = db.query(StudentInvoice).filter_by(id=invoice_id, school_id=school_id).one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found in this school")
    return invoice


def _recalculate_invoice(invoice: StudentInvoice) -> None:
    paid = round(sum(float(payment.amount) for payment in invoice.payments), 2)
    due = float(invoice.amount_due)
    if paid > due + 0.001:
        raise HTTPException(422, "Payments exceed the invoice amount due")
    invoice.amount_paid = paid
    if due == 0 or paid >= due - 0.001:
        invoice.status = "PAID"
    elif paid > 0:
        invoice.status = "PENDING"
    else:
        invoice.status = "NOT_PAID"


@router.patch("/invoices/{invoice_id}")
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    invoice = _invoice_or_404(db, user.school_id, invoice_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)
    _recalculate_invoice(invoice)
    db.commit()
    return {
        "id": invoice.id,
        "description": invoice.description,
        "amount_due": float(invoice.amount_due),
        "amount_paid": float(invoice.amount_paid),
        "status": invoice.status,
    }


@router.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    invoice = _invoice_or_404(db, user.school_id, invoice_id)
    db.delete(invoice)
    db.commit()
    return {"deleted": True, "invoice_id": invoice_id}


@router.get("/student-profiles")
def student_transaction_profiles(user: User = Depends(manager_only), db: Session = Depends(get_db)):
    """Private student transaction profiles — per-learner tuition metrics,
    revenue collected and last payment instrument."""
    students = (
        db.query(Student)
        .options(joinedload(Student.current_class))
        .filter_by(school_id=user.school_id, is_active=True)
        .order_by(Student.last_name, Student.first_name)
        .all()
    )
    invoices = (
        db.query(StudentInvoice)
        .options(joinedload(StudentInvoice.payments))
        .filter_by(school_id=user.school_id)
        .all()
    )
    by_student: dict[int, list[StudentInvoice]] = {}
    for inv in invoices:
        by_student.setdefault(inv.student_id, []).append(inv)

    profiles = []
    for s in students:
        invs = by_student.get(s.id, [])
        billed = sum(float(i.amount_due) for i in invs)
        paid = sum(float(i.amount_paid) for i in invs)
        payments = sorted(
            (p for i in invs for p in i.payments),
            key=lambda p: p.paid_at or dt.datetime.min,
            reverse=True,
        )
        last = payments[0] if payments else None
        profiles.append(
            {
                "student_id": s.id,
                "national_student_id": s.national_student_id,
                "student": f"{s.first_name} {s.last_name}",
                "class_label": (
                    f"{s.current_class.class_level} {s.current_class.class_stream}"
                    if s.current_class
                    else None
                ),
                "invoices": len(invs),
                "total_billed": round(billed, 2),
                "total_paid": round(paid, 2),
                "balance": round(billed - paid, 2),
                "last_payment_at": last.paid_at.isoformat() if last and last.paid_at else None,
                "last_payment_method": last.payment_method if last else None,
            }
        )
    return {"student_profiles": profiles}


@router.post("/invoices/{invoice_id}/payments", status_code=201)
def record_payment(
    invoice_id: int,
    payload: PaymentCreate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    invoice = _invoice_or_404(db, user.school_id, invoice_id)
    new_paid = float(invoice.amount_paid) + payload.amount
    balance = float(invoice.amount_due) - new_paid
    if balance < -0.001:
        raise HTTPException(422, "Payment exceeds the outstanding balance")

    payment = PaymentTransaction(
        school_id=user.school_id,
        invoice_id=invoice.id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        reference_number=payload.reference_number,
        paid_at=dt.datetime.now(),
        received_by=user.id,
    )
    db.add(payment)
    # The relationship may not see the pending child until flush.
    db.flush()
    _recalculate_invoice(invoice)
    db.commit()
    return {
        "payment_id": payment.id,
        "invoice_status": invoice.status,
        "balance": round(float(invoice.amount_due) - float(invoice.amount_paid), 2),
    }


@router.patch("/invoices/{invoice_id}/payments/{payment_id}")
def update_payment(
    invoice_id: int,
    payment_id: int,
    payload: PaymentUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    invoice = _invoice_or_404(db, user.school_id, invoice_id)
    payment = db.query(PaymentTransaction).filter_by(
        id=payment_id, invoice_id=invoice.id, school_id=user.school_id
    ).one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found for this invoice")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(payment, field, value)
    db.flush()
    _recalculate_invoice(invoice)
    db.commit()
    return {
        "payment_id": payment.id,
        "invoice_status": invoice.status,
        "balance": round(float(invoice.amount_due) - float(invoice.amount_paid), 2),
    }


@router.delete("/invoices/{invoice_id}/payments/{payment_id}")
def delete_payment(
    invoice_id: int,
    payment_id: int,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    invoice = _invoice_or_404(db, user.school_id, invoice_id)
    payment = db.query(PaymentTransaction).filter_by(
        id=payment_id, invoice_id=invoice.id, school_id=user.school_id
    ).one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found for this invoice")
    db.delete(payment)
    db.flush()
    _recalculate_invoice(invoice)
    db.commit()
    return {
        "deleted": True,
        "payment_id": payment_id,
        "invoice_status": invoice.status,
        "balance": round(float(invoice.amount_due) - float(invoice.amount_paid), 2),
    }

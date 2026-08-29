"""PRIVATE FINANCIAL ERP TIER — 🔒 CRITICAL FIREWALL ZONE 🔒

These models back tuition_rates / student_invoices / payment_transactions.
No state_inspector API route, service query or serializer ever imports them.
The database-level firewall (sql/002_security_firewall.sql) is the second
line of defence; the router-level dependency guard is the first.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TuitionRate(Base):
    __tablename__ = "tuition_rates"
    __table_args__ = (UniqueConstraint("school_id", "class_level", "billing_cycle", name="uq_tuition_rate"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_level: Mapped[str] = mapped_column(String(50), nullable=False)
    base_tuition_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(30), default="Termly")
    effective_date: Mapped[dt.date | None] = mapped_column(Date)


class StudentInvoice(Base):
    __tablename__ = "student_invoices"
    __table_args__ = (
        CheckConstraint("amount_due >= 0", name="chk_amount_due"),
        Index("idx_invoices_ledger", "school_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    academic_year_id: Mapped[int | None] = mapped_column(ForeignKey("academic_years.id"))
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="Outstanding")
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    student = relationship("Student")
    payments = relationship("PaymentTransaction", back_populates="invoice", cascade="all, delete-orphan")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("student_invoices.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100))
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    invoice = relationship("StudentInvoice", back_populates="payments")


class SecurityAuditLog(Base):
    """Records every ALLOWED/BLOCKED decision at the firewall boundary."""

    __tablename__ = "security_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    role: Mapped[str | None] = mapped_column(String(50))
    endpoint: Mapped[str | None] = mapped_column(String(255))
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

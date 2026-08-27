"""Teacher governance, payroll, qualifications, certifications, exits."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CampusScopedMixin, TimestampMixin
from app.models.types import CertKind, CertState, CourseRole, DegreeLevel, EmploymentState, PayoutState


class Teacher(Base, TimestampMixin, CampusScopedMixin):
    __tablename__ = "teachers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    ne_tid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id"), unique=True
    )
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    national_id_hash: Mapped[str | None] = mapped_column(String(64))
    employment_state: Mapped[str] = mapped_column(EmploymentState, default="active", nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    exit_date: Mapped[date | None] = mapped_column(Date)
    is_civil_service: Mapped[bool] = mapped_column(Boolean, default=True)

    certifications = relationship("TeacherCertification", back_populates="teacher")


class TeacherQualification(Base, CampusScopedMixin):
    __tablename__ = "teacher_qualifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False
    )
    degree_level: Mapped[str] = mapped_column(DegreeLevel, nullable=False)
    field_of_study: Mapped[str] = mapped_column(String, nullable=False)
    institution: Mapped[str] = mapped_column(String, nullable=False)
    awarded_year: Mapped[int] = mapped_column(Integer, nullable=False)
    certificate_no: Mapped[str | None] = mapped_column(String)
    verification_doc: Mapped[bytes | None] = mapped_column(BYTEA)


class TeacherCertification(Base, CampusScopedMixin):
    __tablename__ = "teacher_certifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False
    )
    cert_kind: Mapped[str] = mapped_column(CertKind, nullable=False)
    cert_no: Mapped[str] = mapped_column(String, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(CertState, default="active")
    next_renewal: Mapped[date | None] = mapped_column(Date)
    document: Mapped[bytes | None] = mapped_column(BYTEA)

    teacher = relationship("Teacher", back_populates="certifications")


class TeacherAssignment(Base, CampusScopedMixin):
    __tablename__ = "teacher_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False
    )
    course_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course_sections.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(CourseRole, default="lead", nullable=False)
    weekly_contact_hours: Mapped[float] = mapped_column(Numeric(5, 1), default=0)
    lecture_space_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classrooms.id")
    )
    __table_args__ = (
        UniqueConstraint("teacher_id", "course_section_id", name="uq_teacher_section"),
    )


class CivilServiceGrade(Base):
    __tablename__ = "civil_service_grades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    grade_tier: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    base_salary_naira: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    hardship_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), default=1.0)
    min_years_service: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TeacherPayrollProfile(Base, CampusScopedMixin):
    __tablename__ = "teacher_payroll_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), unique=True, nullable=False
    )
    grade_tier: Mapped[int] = mapped_column(
        Integer, ForeignKey("civil_service_grades.id"), nullable=False
    )
    hardship_zone: Mapped[str | None] = mapped_column(String)
    regional_allowance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    bank_code: Mapped[str | None] = mapped_column(String)
    bank_account_encrypted: Mapped[bytes | None] = mapped_column(BYTEA)
    bank_account_hash: Mapped[str | None] = mapped_column(String(64))
    tin: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    pension_rate: Mapped[float] = mapped_column(Numeric(4, 2), default=7.5)
    is_bank_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_tin_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class TeacherBackgroundLog(Base, CampusScopedMixin):
    __tablename__ = "teacher_background_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False
    )


class TeacherExitRecord(Base, CampusScopedMixin):
    __tablename__ = "teacher_exit_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False
    )
    exit_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    clearance_doc: Mapped[bytes | None] = mapped_column(BYTEA)
    last_pay_period: Mapped[str | None] = mapped_column(String)
    signed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("managers.id"), nullable=False
    )


class PayrollEntry(Base, CampusScopedMixin):
    __tablename__ = "payroll_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False
    )
    pay_period: Mapped[str] = mapped_column(String, nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(6, 1), default=0)
    base_pay: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    hardship_allowance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    gross: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    pension_deduction: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    net: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(PayoutState, default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("teacher_id", "pay_period", name="uq_payroll_teacher_period"),
    )

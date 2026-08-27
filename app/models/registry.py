"""Student registry, mobility matrix, enrollments."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CampusScopedMixin, TimestampMixin
from app.models.types import EnrollmentKind, Gender, MobilityEdge, PersonStatus, TermType, TransferState


class Student(Base, TimestampMixin, CampusScopedMixin):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    ne_sid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    national_id_hash: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(Gender, nullable=False)
    enrollment_kind: Mapped[str] = mapped_column(EnrollmentKind, default="k12", nullable=False)
    current_major: Mapped[str | None] = mapped_column(String)
    current_grade_level: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(PersonStatus, default="active", nullable=False)
    guardian_name: Mapped[str | None] = mapped_column(String)
    guardian_phone: Mapped[str | None] = mapped_column(String)
    matriculated_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    is_dual_enrollment_suspect: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    mobility = relationship("StudentMobility", back_populates="student")


class StudentMobility(Base):
    """Chronological schooling-history tree; protects against dual enrolment."""

    __tablename__ = "student_mobility"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    campus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campus.id"), nullable=False
    )
    from_campus_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campus.id")
    )
    to_campus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campus.id"), nullable=False
    )
    from_enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id")
    )
    to_enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrollments.id")
    )
    previous_mobility_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_mobility.id")
    )
    edge_type: Mapped[str] = mapped_column(MobilityEdge, default="horizontal_transfer", nullable=False)
    transfer_state: Mapped[str] = mapped_column(TransferState, default="drafted", nullable=False)
    requested_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    effective_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    signed_manifest: Mapped[bytes | None] = mapped_column(BYTEA)

    student = relationship("Student", back_populates="mobility")
    clearances = relationship("TransferClearance", back_populates="mobility")


class TransferClearance(Base):
    __tablename__ = "transfer_clearances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    mobility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_mobility.id"), nullable=False
    )
    campus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campus.id"), nullable=False
    )
    clearance_type: Mapped[str] = mapped_column(String, nullable=False)
    issued_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("managers.id"), nullable=False
    )
    clearance_state: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    signed_document: Mapped[bytes] = mapped_column(BYTEA, nullable=False)

    mobility = relationship("StudentMobility", back_populates="clearances")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    campus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campus.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("terms.id"))
    major_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("majors.id"))
    grade_level: Mapped[str | None] = mapped_column(String)
    section_name: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(PersonStatus, default="active", nullable=False)
    matriculated_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    label: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)


class Term(Base):
    __tablename__ = "terms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False
    )
    term_type: Mapped[str] = mapped_column(TermType, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    __table_args__ = (
        UniqueConstraint("academic_year_id", "term_type", name="uq_terms_year_type"),
    )

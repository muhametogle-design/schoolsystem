"""Platform identity, tenant configuration, and user profiles."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PrivateSchool(Base):
    """One independently managed school tenant.

    ``school_code`` is the immutable short code used as the prefix for every
    student roll number (for example ``NG-10023``). Billing contact fields are
    intentionally kept on the tenant record but are never serialized by a
    state-facing API.
    """

    __tablename__ = "private_schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_license_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    school_code: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    proprietor_name: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    physical_address: Mapped[str | None] = mapped_column(Text)
    accreditation_status: Mapped[str] = mapped_column(String(50), default="Active")

    # Tenant-private billing profile. State routes must not expose these values.
    billing_contact_name: Mapped[str | None] = mapped_column(String(255))
    billing_phone: Mapped[str | None] = mapped_column(String(50))
    billing_email: Mapped[str | None] = mapped_column(String(255))
    billing_address: Mapped[str | None] = mapped_column(Text)
    billing_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    classes = relationship("SchoolClass", back_populates="school", cascade="all, delete-orphan")
    roll_sequence = relationship(
        "SchoolRollSequence", back_populates="school", cascade="all, delete-orphan", uselist=False
    )


class SchoolRollSequence(Base):
    """Locked per-school roll-number allocator owned by State Admins.

    The value is updated in the same transaction as student creation. This is
    deliberately not derived from a student count, which means a withdrawn
    student never causes a roll number to be re-issued.
    """

    __tablename__ = "school_roll_sequences"

    school_id: Mapped[int] = mapped_column(
        ForeignKey("private_schools.id", ondelete="CASCADE"), primary_key=True
    )
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    updated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    school = relationship("PrivateSchool", back_populates="roll_sequence")


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # state_admin / inspector (state-wide) | school_manager / teacher (tenant)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))

    # NE-MID (managers) / NE-TID (teachers), retained as internal staff IDs.
    staff_identifier: Mapped[str | None] = mapped_column(String(30), unique=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    qualifications: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str | None] = mapped_column(String(100))
    bio: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    school = relationship("PrivateSchool")
    teaching_assignments = relationship(
        "TeachingAssignment",
        back_populates="teacher",
        foreign_keys="TeachingAssignment.teacher_id",
    )

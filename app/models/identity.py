"""Platform configuration & state accreditation core (Phase 1 tier 1)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PrivateSchool(Base):
    __tablename__ = "private_schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_license_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    proprietor_name: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    physical_address: Mapped[str | None] = mapped_column(Text)
    accreditation_status: Mapped[str] = mapped_column(String(50), default="Active")
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    classes = relationship("SchoolClass", back_populates="school", cascade="all, delete-orphan")


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
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # state_inspector / school_manager / teacher
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))

    # NE-MID (managers) / NE-TID (teachers) — issued by
    # app.services.student_id.generate_unique_staff_identifier.
    staff_identifier: Mapped[str | None] = mapped_column(String(30), unique=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    qualifications: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str | None] = mapped_column(String(100))  # e.g. "Principal"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    school = relationship("PrivateSchool")

"""Course / classroom / academic-artifact models (NE-CID, grades, attendance)."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CampusScopedMixin, TimestampMixin
from app.models.types import (
    AttendanceStatus,
    DataSource,
    GradeBand,
    IncidentKind,
    IncidentLevel,
    PersonStatus,
)


class StateCurricula(Base):
    __tablename__ = "state_curricula"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    subject_code: Mapped[str] = mapped_column(String, nullable=False)
    subject_name: Mapped[str] = mapped_column(String, nullable=False)
    curriculum_version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        UniqueConstraint(
            "state_code", "subject_code", "curriculum_version", name="uq_curriculum"
        ),
    )


class Classroom(Base, CampusScopedMixin):
    __tablename__ = "classrooms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    room_code: Mapped[str] = mapped_column(String, nullable=False)
    building: Mapped[str | None] = mapped_column(String)
    capacity: Mapped[int] = mapped_column(Integer, default=40)
    is_laboratory: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("campus_id", "room_code", name="uq_classroom_room"),)


class CourseSection(Base, CampusScopedMixin):
    """NE-CID: state curriculum bound to a campus section + classroom."""

    __tablename__ = "course_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    ne_cid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("state_curricula.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id"), nullable=False
    )
    classroom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classrooms.id"), nullable=False
    )
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id")
    )
    section_code: Mapped[str] = mapped_column(String, nullable=False)
    enrolled_count: Mapped[int] = mapped_column(Integer, default=0)
    weekly_contact_hours: Mapped[float] = mapped_column(Numeric(5, 1), default=0)
    schedule_json: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        UniqueConstraint(
            "campus_id",
            "curriculum_id",
            "academic_year_id",
            "term_id",
            "section_code",
            name="uq_section_composite",
        ),
    )


class CourseEnrollment(Base, CampusScopedMixin):
    __tablename__ = "course_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    course_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course_sections.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(PersonStatus, default="active", nullable=False)
    enrolled_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    __table_args__ = (
        UniqueConstraint("student_id", "course_section_id", name="uq_student_section"),
    )


class Transcript(Base):
    __tablename__ = "transcripts"

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
    cumulative_gpa: Mapped[float] = mapped_column(Numeric(4, 2), default=0)
    credits_earned: Mapped[float] = mapped_column(Numeric(6, 1), default=0)
    class_rank: Mapped[int | None] = mapped_column(Integer)
    is_inherited: Mapped[bool] = mapped_column(Boolean, default=False)
    source_sin: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transcripts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ExamSheet(Base, CampusScopedMixin):
    __tablename__ = "exam_sheets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    course_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course_sections.id"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    exam_type: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    grade_band: Mapped[str | None] = mapped_column(GradeBand)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint(
            "course_section_id", "student_id", "exam_type", name="uq_exam_sheet"
        ),
    )


class Attendance(Base, CampusScopedMixin):
    __tablename__ = "attendance"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    course_section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course_sections.id")
    )
    attendance_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    status: Mapped[str] = mapped_column(AttendanceStatus, nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    clerk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(DataSource, default="portal", nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("student_id", "course_section_id", "attendance_date", name="uq_attendance"),
    )


class IncidentReport(Base, CampusScopedMixin):
    __tablename__ = "incident_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    incident_date: Mapped[date] = mapped_column(Date, default=date.today)
    kind: Mapped[str] = mapped_column(IncidentKind, nullable=False)
    severity: Mapped[str] = mapped_column(IncidentLevel, default="low", nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    reported_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("managers.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(PersonStatus, default="active")


class TruancyMark(Base, CampusScopedMixin):
    __tablename__ = "truancy_marks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False
    )
    unexcused_absences: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_misses: Mapped[int] = mapped_column(Integer, default=0)
    is_chronic: Mapped[bool] = mapped_column(Boolean, default=False)
    last_recomputed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

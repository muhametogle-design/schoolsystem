"""Compliance tier: classes 1-12, curriculum assignments, students, grades and attendance."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

CLASS_LEVELS = tuple(f"Class {n}" for n in range(1, 13))
ATTENDANCE_STATUSES = ("Present", "Absent", "Late", "Excused")

#: Tuition fee standing for a student, surfaced by the Tuition Status
#: Breakdown widget on the School Manager dashboard. `SCHOLARSHIP` covers
#: fully sponsored students who owe nothing but are not "PAID" in cash terms.
FEE_STATUSES = ("PAID", "PENDING", "NOT_PAID", "SCHOLARSHIP")


class SchoolClass(Base):
    __tablename__ = "school_classes"
    __table_args__ = (
        CheckConstraint(
            "class_level IN (%s)" % ", ".join(f"'{c}'" for c in CLASS_LEVELS), name="chk_class_level"
        ),
        UniqueConstraint("school_id", "class_level", "class_stream", name="uq_class_per_school"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_level: Mapped[str] = mapped_column(String(50), nullable=False)
    class_stream: Mapped[str] = mapped_column(String(50), nullable=False)
    room_number: Mapped[str | None] = mapped_column(String(50))
    class_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    school = relationship("PrivateSchool", back_populates="classes")
    students = relationship("Student", back_populates="current_class")
    teaching_assignments = relationship(
        "TeachingAssignment",
        back_populates="school_class",
        foreign_keys="TeachingAssignment.class_id",
        cascade="all, delete-orphan",
    )


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        Index("idx_student_search_national_id", "national_student_id"),
        Index("idx_student_search_roll_number", "roll_number"),
        Index("idx_student_names", "last_name", "first_name"),
        Index("idx_student_fee_status", "school_id", "fee_status"),
        CheckConstraint(
            "gender IN ('Male', 'Female', 'Other') OR gender IS NULL", name="chk_gender"
        ),
        CheckConstraint(
            "fee_status IN (%s) OR fee_status IS NULL" % ", ".join(f"'{s}'" for s in FEE_STATUSES),
            name="chk_fee_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    # Retained for API compatibility; all new registrations use their roll number here too.
    national_student_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    roll_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    current_class_id: Mapped[int | None] = mapped_column(ForeignKey("school_classes.id", ondelete="SET NULL"))
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[dt.date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    guardian_name: Mapped[str | None] = mapped_column(String(255))
    guardian_relationship: Mapped[str | None] = mapped_column(String(50))
    guardian_phone: Mapped[str | None] = mapped_column(String(50))
    guardian_email: Mapped[str | None] = mapped_column(String(255))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(50))
    physical_address: Mapped[str | None] = mapped_column(Text)
    #: PAID | PENDING | NOT_PAID | SCHOLARSHIP — drives the fee collection matrix.
    fee_status: Mapped[str] = mapped_column(String(20), default="NOT_PAID", nullable=False)
    #: Profile photo as a data-URL (or CDN URL). Uploads are manager-gated.
    photo_url: Mapped[str | None] = mapped_column(Text)
    enrollment_date: Mapped[dt.date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    school = relationship("PrivateSchool")
    current_class = relationship("SchoolClass", back_populates="students")


class Subject(Base):
    """A subject catalog entry at a school and class level.

    A separate ``TeachingAssignment`` ties it to a particular stream and
    teacher. Keeping the catalogue separate means Class 7 A and Class 7 B can
    use the same curriculum while having different subject teachers.
    """

    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("school_id", "subject_code", "class_level", name="uq_subject_per_school"),
        CheckConstraint(
            "class_level IN (%s)" % ", ".join(f"'{c}'" for c in CLASS_LEVELS), name="chk_subject_class_level"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    subject_code: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(150), nullable=False)
    class_level: Mapped[str] = mapped_column(String(50), nullable=False)

    teaching_assignments = relationship(
        "TeachingAssignment",
        back_populates="subject",
        foreign_keys="TeachingAssignment.subject_id",
        cascade="all, delete-orphan",
    )


class TeachingAssignment(Base):
    """Authoritative class / subject / teacher mapping.

    Grade-entry history is deliberately *not* used to infer who teaches a
    subject. This table is the schedule source of truth for school managers,
    State Admins, and Inspectors.
    """

    __tablename__ = "teaching_assignments"
    __table_args__ = (
        UniqueConstraint("school_id", "class_id", "subject_id", name="uq_class_subject_assignment"),
        Index("idx_teaching_assignments_teacher", "school_id", "teacher_id"),
        Index("idx_teaching_assignments_class", "school_id", "class_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    # The foreign key stays nullable for a migration-safe schema, while the
    # management service reassigns a departing teacher before removal so every
    # operational class subject continues to have an explicit instructor.
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    school_class = relationship("SchoolClass", back_populates="teaching_assignments", foreign_keys=[class_id])
    subject = relationship("Subject", back_populates="teaching_assignments", foreign_keys=[subject_id])
    teacher = relationship("User", back_populates="teaching_assignments", foreign_keys=[teacher_id])


class StudentGrade(Base):
    """Continuous assessment marks. PRIVATE draft until `is_published` flips."""

    __tablename__ = "student_grades"
    __table_args__ = (
        CheckConstraint("numeric_score >= 0 AND numeric_score <= 100", name="chk_score_range"),
        UniqueConstraint("student_id", "subject_id", "academic_year_id", "exam_name", name="uq_grade_record"),
        Index("idx_grades_lookup", "school_id", "class_id", "subject_id"),
        Index("idx_grades_publication_valve", "is_published", "school_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    exam_name: Mapped[str] = mapped_column(String(150), nullable=False)
    numeric_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    student = relationship("Student")
    subject = relationship("Subject")


class ExamSubmissionEvent(Base):
    """Immutable record registered when a school hits 'Publish Exam Marks to State'."""

    __tablename__ = "exam_submission_events"
    __table_args__ = (Index("idx_exam_events_school", "school_id", "published_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    exam_name: Mapped[str] = mapped_column(String(150), nullable=False)
    records_released: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())


class LiveAttendance(Base):
    __tablename__ = "live_attendance"
    __table_args__ = (
        CheckConstraint(
            "status IN (%s)" % ", ".join(f"'{s}'" for s in ATTENDANCE_STATUSES),
            name="chk_attendance_status",
        ),
        UniqueConstraint("student_id", "date", name="uq_attendance_per_day"),
        Index("idx_attendance_compliance", "date", "school_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    student = relationship("Student")


class DailySubmissionLog(Base):
    __tablename__ = "daily_submission_logs"
    __table_args__ = (
        UniqueConstraint("school_id", "log_date", name="uq_daily_log"),
        Index("idx_compliance_tracker", "log_date", "alarm_triggered"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    log_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    attendance_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    attendance_submitted_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    alarm_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    alarm_raised_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    school = relationship("PrivateSchool")


class CommunicationLog(Base):
    __tablename__ = "communication_logs"
    __table_args__ = (
        CheckConstraint(
            "delivery_status IN ('Pending', 'Sent', 'Delivered', 'Failed')",
            name="chk_delivery_status",
        ),
        Index("idx_comm_logs_type", "message_type", "timestamp_sent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"))
    recipient_phone: Mapped[str | None] = mapped_column(String(50))
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(20), default="Pending")
    timestamp_sent: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

"""Operations tier — production modules: substitution engine, syllabus
tracking, encrypted backups, and biometric hardware management.

These tables extend the tenant ERP without touching the compliance or private
financial tiers. Every tenant-owned row carries ``school_id`` so the existing
route-level tenancy predicates (and PostgreSQL RLS) keep working unchanged.
"""

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
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# ---------------------------------------------------------------------------
# Module 1 — Teacher absence & substitution engine
# ---------------------------------------------------------------------------

ABSENCE_STATUSES = ("logged", "covered", "cancelled")
SUBSTITUTION_STATUSES = ("open", "confirmed", "completed")

#: A school week runs Monday (0) .. Sunday (6); the seeded timetable uses 0-4.
TIMETABLE_DAYS = tuple(range(7))
TIMETABLE_PERIODS = tuple(range(1, 9))


class TimetableSlot(Base):
    """One period of the weekly timetable: a class meets a subject/teacher.

    Two hard uniqueness rules make the substitution engine sound:

    * a class cannot be in two rooms at the same (day, period);
    * a teacher cannot teach two classes at the same (day, period).

    The second rule is what "unassigned period slots" means for candidate
    matching — a teacher who already occupies a period cannot cover an absent
    colleague at that time.
    """

    __tablename__ = "timetable_slots"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="chk_timetable_day"),
        CheckConstraint("period_number BETWEEN 1 AND 8", name="chk_timetable_period"),
        UniqueConstraint(
            "school_id", "class_id", "day_of_week", "period_number", name="uq_timetable_class_period"
        ),
        UniqueConstraint(
            "school_id", "teacher_id", "day_of_week", "period_number", name="uq_timetable_teacher_period"
        ),
        Index("idx_timetable_teacher_day", "school_id", "teacher_id", "day_of_week"),
        Index("idx_timetable_class_day", "school_id", "class_id", "day_of_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)

    school_class = relationship("SchoolClass")
    subject = relationship("Subject")
    teacher = relationship("User")


class TeacherAbsence(Base):
    """A logged absence for one teacher on one date.

    Trigger point for the coverage recommendation panel: logging a row here
    arms the engine, which projects the teacher's timetable slots for that
    date and matches substitutes in real time.
    """

    __tablename__ = "teacher_absences"
    __table_args__ = (
        CheckConstraint(
            "status IN (%s)" % ", ".join(f"'{s}'" for s in ABSENCE_STATUSES), name="chk_absence_status"
        ),
        UniqueConstraint("school_id", "teacher_id", "absence_date", name="uq_absence_per_teacher_day"),
        Index("idx_absences_school_date", "school_id", "absence_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    absence_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    #: logged -> covered (every slot has a confirmed substitute) / cancelled
    status: Mapped[str] = mapped_column(String(20), default="logged", nullable=False)
    logged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    teacher = relationship("User", foreign_keys=[teacher_id])
    substitutions = relationship(
        "SubstitutionAssignment", back_populates="absence", cascade="all, delete-orphan"
    )


class SubstitutionAssignment(Base):
    """A confirmed (or still-open) cover for one absent teacher slot."""

    __tablename__ = "substitution_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN (%s)" % ", ".join(f"'{s}'" for s in SUBSTITUTION_STATUSES),
            name="chk_substitution_status",
        ),
        UniqueConstraint("absence_id", "period_number", "class_id", name="uq_substitution_per_slot"),
        Index("idx_substitutions_school_date", "school_id", "date_for_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    absence_id: Mapped[int] = mapped_column(
        ForeignKey("teacher_absences.id", ondelete="CASCADE"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    original_teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    substitute_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    #: The engine stores the ISO weekday index of the absence for reporting.
    date_for_day: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    #: Engine transparency: the matcher score and human-readable reasons that
    #: produced this recommendation are frozen into the confirmed row.
    match_score: Mapped[int | None] = mapped_column(Integer)
    match_reason: Mapped[str | None] = mapped_column(Text)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    absence = relationship("TeacherAbsence", back_populates="substitutions")
    school_class = relationship("SchoolClass")
    subject = relationship("Subject")
    substitute = relationship("User", foreign_keys=[substitute_teacher_id])


# ---------------------------------------------------------------------------
# Module 2 — Syllabus completion tracker (Classes 1-12)
# ---------------------------------------------------------------------------

SYLLABUS_STATUSES = ("On Track", "Ahead", "Behind Schedule")


class SyllabusPlan(Base):
    """Curriculum pacing contract for one class + subject + term.

    ``total_units`` is the full syllabus size. ``midterm_target_pct`` and
    ``final_target_pct`` are the benchmark gates the tracker measures actual
    progress against; the pace engine interpolates the expected completion
    percentage for any date between term start, midterm and term end.
    """

    __tablename__ = "syllabus_plans"
    __table_args__ = (
        CheckConstraint("total_units > 0", name="chk_syllabus_total_units"),
        CheckConstraint(
            "midterm_target_pct >= 0 AND midterm_target_pct <= 100", name="chk_syllabus_midterm_target"
        ),
        CheckConstraint(
            "final_target_pct >= 0 AND final_target_pct <= 100", name="chk_syllabus_final_target"
        ),
        UniqueConstraint("school_id", "class_id", "subject_id", "term", name="uq_syllabus_plan"),
        Index("idx_syllabus_plans_school", "school_id", "term"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    term: Mapped[str] = mapped_column(String(50), default="Term 1", nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    midterm_target_pct: Mapped[float] = mapped_column(Integer, default=45, nullable=False)
    final_target_pct: Mapped[float] = mapped_column(Integer, default=100, nullable=False)
    term_start: Mapped[dt.date | None] = mapped_column(Date)
    midterm_date: Mapped[dt.date | None] = mapped_column(Date)
    term_end: Mapped[dt.date | None] = mapped_column(Date)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    school_class = relationship("SchoolClass")
    subject = relationship("Subject")
    entries = relationship(
        "SyllabusProgressEntry", back_populates="plan", cascade="all, delete-orphan"
    )
    topics = relationship("SyllabusTopic", back_populates="plan", cascade="all, delete-orphan")


class SyllabusProgressEntry(Base):
    """An audited progress checkpoint: cumulative units completed as of a date.

    Entries are checkpoints, not deltas — the latest entry (by date, then id)
    is the authoritative completion figure, which keeps manual corrections and
    out-of-order entries unambiguous.
    """

    __tablename__ = "syllabus_progress_entries"
    __table_args__ = (
        CheckConstraint("units_after >= 0", name="chk_syllabus_units_nonnegative"),
        Index("idx_syllabus_entries_plan", "plan_id", "entry_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("syllabus_plans.id", ondelete="CASCADE"), nullable=False)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    entry_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    units_after: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    plan = relationship("SyllabusPlan", back_populates="entries")


class SyllabusTopic(Base):
    """One national-curriculum unit inside a syllabus plan.

    Topics are what the "Log Topic Covered" modal ticks off. The order of the
    tick log feeds the audited progress checkpoints, keeping the percentage
    and the ticked units always reconcilable.
    """

    __tablename__ = "syllabus_topics"
    __table_args__ = (
        Index("idx_syllabus_topics_plan", "plan_id", "position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("syllabus_plans.id", ondelete="CASCADE"), nullable=False)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    code: Mapped[str | None] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    done_date: Mapped[dt.date | None] = mapped_column(Date)
    done_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    plan = relationship("SyllabusPlan", back_populates="topics")


# ---------------------------------------------------------------------------
# Module 4 — Automated encrypted backups
# ---------------------------------------------------------------------------


class DataChangeLog(Base):
    """Row-level change feed written by database triggers.

    The JSON delta export reads everything newer than the last snapshot's
    high-water mark (``id``), so a midnight delta is exactly the day's changes.
    Triggers are installed for the SQLite tier by ``init_db`` (generated from
    the ORM metadata) and for PostgreSQL by ``sql/004_ops_modules.sql``.
    """

    __tablename__ = "data_change_log"
    __table_args__ = (Index("idx_change_log_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    row_pk: Mapped[str] = mapped_column(String(64), nullable=False)
    #: I / U / D
    operation: Mapped[str] = mapped_column(String(1), nullable=False)
    changed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    #: JSON object of the affected row (NEW for I/U, OLD for D).
    payload: Mapped[str | None] = mapped_column(Text)


class BackupRecord(Base):
    """One produced backup artefact and its integrity metadata."""

    __tablename__ = "backup_records"
    __table_args__ = (
        CheckConstraint("kind IN ('full_snapshot', 'json_delta')", name="chk_backup_kind"),
        CheckConstraint("status IN ('completed', 'failed')", name="chk_backup_status"),
        Index("idx_backup_records_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    md5: Mapped[str | None] = mapped_column(String(32))
    encrypted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    encryption: Mapped[str | None] = mapped_column(String(50), default="AES-256-GCM")
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    triggered_by: Mapped[str | None] = mapped_column(String(20), default="scheduled")
    #: High-water mark of data_change_log covered by a delta export.
    delta_rows: Mapped[int | None] = mapped_column(Integer)
    last_change_id: Mapped[int | None] = mapped_column(Integer)
    #: Compact per-table row counts captured at snapshot time (JSON text).
    row_counts: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    audit_events = relationship("BackupAuditEvent", back_populates="backup")


class BackupAuditEvent(Base):
    """Admin audit trail: every backup production, download and verification."""

    __tablename__ = "backup_audit_events"
    __table_args__ = (Index("idx_backup_audit_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backup_id: Mapped[int | None] = mapped_column(ForeignKey("backup_records.id", ondelete="SET NULL"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    #: created | downloaded | decrypted_download | verified | verify_failed | failed | purged
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())

    backup = relationship("BackupRecord", back_populates="audit_events")
    actor = relationship("User")


# ---------------------------------------------------------------------------
# Module 5 — Biometric hardware management (WebAuthn)
# ---------------------------------------------------------------------------

BIOMETRIC_OWNER_TYPES = ("student", "staff")
BIOMETRIC_METHODS = ("fingerprint", "smartcard", "platform", "usb_key", "simulated")
CREDENTIAL_STATUSES = ("active", "revoked")
VERIFICATION_PURPOSES = ("exam_hall_entry", "staff_attendance", "enrollment_check")
VERIFICATION_RESULTS = ("success", "failed", "unknown_credential", "revoked_credential")
BACKUP_KINDS = ("full_snapshot", "json_delta")
#: Convenience alias so API layers can validate without importing the tuple
#: under a different name than the model registry exposes.
VerificationResult = tuple(VERIFICATION_RESULTS)  # type: ignore[assignment]


class BiometricCredential(Base):
    """A registered WebAuthn credential (fingerprint reader, smartcard, …).

    ``public_key`` stores the COSE key the authenticator returned at
    registration; assertions are verified against it with the signature
    counter tracked in ``sign_count`` for clone detection.
    """

    __tablename__ = "biometric_credentials"
    __table_args__ = (
        CheckConstraint(
            "owner_type IN (%s)" % ", ".join(f"'{t}'" for t in BIOMETRIC_OWNER_TYPES),
            name="chk_biometric_owner_type",
        ),
        CheckConstraint(
            "status IN (%s)" % ", ".join(f"'{s}'" for s in CREDENTIAL_STATUSES),
            name="chk_biometric_credential_status",
        ),
        Index("idx_biometric_credentials_owner", "owner_type", "owner_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"))
    owner_type: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    credential_id: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    #: Base64 COSE key payload.
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    aaguid: Mapped[str | None] = mapped_column(String(36))
    transports: Mapped[str | None] = mapped_column(String(120))
    device_type: Mapped[str | None] = mapped_column(String(50))
    method: Mapped[str | None] = mapped_column(String(20), default="fingerprint")
    label: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class BiometricVerificationLog(Base):
    """Immutable verification feed for exam-hall entry and staff attendance."""

    __tablename__ = "biometric_verification_logs"
    __table_args__ = (
        CheckConstraint(
            "purpose IN (%s)" % ", ".join(f"'{p}'" for p in VERIFICATION_PURPOSES),
            name="chk_biometric_purpose",
        ),
        CheckConstraint(
            "result IN (%s)" % ", ".join(f"'{r}'" for r in VERIFICATION_RESULTS),
            name="chk_biometric_result",
        ),
        Index("idx_biometric_logs_school_time", "school_id", "verified_at"),
        Index("idx_biometric_logs_owner", "owner_type", "owner_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"))
    owner_type: Mapped[str | None] = mapped_column(String(10))
    owner_id: Mapped[int | None] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    result: Mapped[str] = mapped_column(String(30), nullable=False)
    credential_id: Mapped[str | None] = mapped_column(String(512))
    #: Denormalised display name so the log survives later profile edits.
    person_label: Mapped[str | None] = mapped_column(String(255))
    detail: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    operated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


# ---------------------------------------------------------------------------
# Refinement 3 — subject-restricted attendance marking engine
# ---------------------------------------------------------------------------

SUBJECT_ATTENDANCE_STATUSES = ("Present", "Absent", "Late", "Excused")


class SubjectAttendance(Base):
    """Attendance for one student in ONE subject period.

    The daily class roster (``live_attendance``) stays the compliance source
    of truth; this table records the finer subject-period marking that the
    subject-restricted engine writes. Uniqueness is per student + date +
    subject + period, so re-marking the same period updates in place.
    """

    __tablename__ = "subject_attendance"
    __table_args__ = (
        CheckConstraint(
            "status IN (%s)" % ", ".join(f"'{s}'" for s in SUBJECT_ATTENDANCE_STATUSES),
            name="chk_subject_attendance_status",
        ),
        UniqueConstraint(
            "student_id", "date", "subject_id", "period_number", name="uq_subject_attendance_slot"
        ),
        Index("idx_subject_attendance_slot", "school_id", "date", "subject_id", "period_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

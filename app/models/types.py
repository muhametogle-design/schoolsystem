"""SQLAlchemy Enum column types mirroring PostgreSQL ENUMs.

``create_type=False`` is critical: the DDL in ``sql/001_schema.sql`` owns the
type; the ORM only reads/writes the existing native enum.
"""

from __future__ import annotations

from sqlalchemy import Enum

CampusType = Enum(
    "pre_primary", "primary", "secondary", "tvet", "tertiary", "adult_ed",
    name="campus_type", create_type=False,
)
Gender = Enum("male", "female", "other", name="gender", create_type=False)
PersonStatus = Enum(
    "active", "suspended", "withdrawn", "transferred", "graduated", "expired", "deceased",
    name="person_status", create_type=False,
)
EnrollmentKind = Enum(
    "k12", "tvet", "higher_education", "adult", name="enrollment_kind", create_type=False
)
TermType = Enum(
    "first", "second", "third", "semester_a", "semester_b", "summer", "full_year",
    name="term_type", create_type=False,
)
TransferState = Enum(
    "none", "drafted", "in_progress", "approved", "cleared", "rejected",
    name="transfer_state", create_type=False,
)
MobilityEdge = Enum(
    "promotion", "horizontal_transfer", "upgrade", "downgrade", "re-entry",
    name="mobility_edge", create_type=False,
)
EmploymentState = Enum(
    "active", "on_leave", "suspended", "transferred", "retired", "terminated",
    name="employment_state", create_type=False,
)
DegreeLevel = Enum(
    "certificate", "diploma", "bachelors", "masters", "doctorate", "other",
    name="degree_level", create_type=False,
)
CertState = Enum(
    "pending", "active", "suspended", "revoked", "expired", name="cert_state", create_type=False
)
CertKind = Enum(
    "teaching_license", "police_clearance", "safety_certificate", "special_education", "other",
    name="cert_kind", create_type=False,
)
AttendanceStatus = Enum(
    "present", "absent", "late", "excused", "truant", name="attendance_status", create_type=False
)
IncidentKind = Enum(
    "academic", "behavioral", "safety", "bullying", "substance", "other",
    name="incident_kind", create_type=False,
)
IncidentLevel = Enum("low", "medium", "high", "critical", name="incident_level", create_type=False)
GradeBand = Enum("A", "B", "C", "D", "E", "F", "NG", name="grade_band", create_type=False)
CourseRole = Enum("lead", "co_teacher", "support", "invigilator", name="course_role", create_type=False)
BatchState = Enum(
    "queued", "running", "completed", "failed", "cancelled", name="batch_state", create_type=False
)
PayoutState = Enum(
    "pending", "approved", "paid", "failed", "void", "reversed",
    name="payout_state", create_type=False,
)
FundingKind = Enum(
    "capitation", "teacher_payroll", "hardship_allowance", "infrastructure",
    "program_based", "emergency", name="funding_kind", create_type=False,
)
SignatureScheme = Enum("ed25519", "rs256", "es256", name="signature_scheme", create_type=False)
DataSource = Enum("portal", "mobile", "api", "batch", "legacy", name="data_source", create_type=False)
LockEntity = Enum(
    "attendance", "exam_sheet", "grade", "payroll_entry", "teacher_profile",
    "classroom", "course_section", "student_record", name="lock_entity", create_type=False,
)
LockState = Enum("unlocked", "locked", name="lock_state", create_type=False)

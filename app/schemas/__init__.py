"""Pydantic request/response contracts."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth ---
class LoginRequest(BaseModel):
    """Two accepted credential styles (refinement 2):

    * email + password — the classic flow for every role;
    * staff_identifier + pin — the dedicated teacher/staff login.

    ``password`` is optional only when the Staff-ID + PIN path is used.
    """

    email: EmailStr | None = None
    password: str | None = None
    staff_identifier: str | None = Field(default=None, min_length=3, max_length=30)
    pin: str | None = Field(default=None, min_length=4, max_length=12)


class UserInfo(BaseModel):
    id: int
    email: str
    role: str
    school_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    school_name: str | None = None
    # Refinement 1: teaching staff with syllabus topic authority.
    is_department_head: bool = False
    staff_identifier: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


# --- Students ---
class StudentCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    current_class_id: int
    date_of_birth: dt.date | None = None
    gender: str | None = Field(default=None, pattern="^(Male|Female|Other)$")
    guardian_name: str | None = None
    guardian_relationship: str | None = None
    guardian_phone: str | None = None
    guardian_email: str | None = None
    emergency_contact_phone: str | None = None
    physical_address: str | None = None
    fee_status: str = Field(default="NOT_PAID", pattern="^(PAID|PENDING|NOT_PAID|SCHOLARSHIP)$")
    # Retained for older clients; roll numbers are school-sequence based now.
    enrollment_year: str = Field(default="2026", pattern="^[0-9]{4}$")


class StudentRead(BaseModel):
    id: int
    school_id: int
    national_student_id: str
    roll_number: str | None = None
    current_class_id: int | None
    class_label: str | None = None
    first_name: str
    last_name: str
    date_of_birth: dt.date | None
    gender: str | None
    guardian_name: str | None
    guardian_relationship: str | None
    guardian_phone: str | None
    guardian_email: str | None
    emergency_contact_phone: str | None
    is_active: bool


# --- Student profile editing ---
FEE_STATUS_VALUES = ("PAID", "PENDING", "NOT_PAID", "SCHOLARSHIP")


class StudentUpdate(BaseModel):
    """Partial update payload for the Student Details page / create drawer."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    current_class_id: int | None = None
    date_of_birth: dt.date | None = None
    gender: str | None = Field(default=None, pattern="^(Male|Female|Other)$")
    guardian_name: str | None = None
    guardian_relationship: str | None = None
    guardian_phone: str | None = None
    guardian_email: str | None = None
    emergency_contact_phone: str | None = None
    physical_address: str | None = None
    fee_status: str | None = Field(default=None, pattern="^(PAID|PENDING|NOT_PAID|SCHOLARSHIP)$")
    is_active: bool | None = None


# --- Classes / subjects / authoritative teaching assignments ---
class ClassCreate(BaseModel):
    class_level: str
    class_stream: str = Field(min_length=1, max_length=50)
    room_number: str | None = Field(default=None, max_length=50)
    class_teacher_id: int | None = None


class ClassUpdate(BaseModel):
    class_stream: str | None = Field(default=None, min_length=1, max_length=50)
    room_number: str | None = Field(default=None, max_length=50)
    class_teacher_id: int | None = None


class SubjectCreate(BaseModel):
    subject_code: str = Field(min_length=1, max_length=30)
    subject_name: str = Field(min_length=1, max_length=150)
    class_level: str
    teacher_id: int | None = None


class SubjectUpdate(BaseModel):
    subject_code: str | None = Field(default=None, min_length=1, max_length=30)
    subject_name: str | None = Field(default=None, min_length=1, max_length=150)


class TeachingAssignmentUpdate(BaseModel):
    teacher_id: int


# --- Teacher profiles ---
class TeacherCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    phone: str | None = Field(default=None, max_length=50)
    qualifications: str | None = None
    designation: str | None = Field(default="Teacher", max_length=100)
    bio: str | None = None
    is_active: bool = True


class TeacherUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=256)
    phone: str | None = Field(default=None, max_length=50)
    qualifications: str | None = None
    designation: str | None = Field(default=None, max_length=100)
    bio: str | None = None
    is_active: bool | None = None


# --- State tenant provisioning / tenant profile ---
class SchoolCreate(BaseModel):
    # State provisioning accepts academic/public tenant setup only. Reject an
    # attempted billing field rather than silently treating it as harmless.
    model_config = ConfigDict(extra="forbid")

    school_name: str = Field(min_length=2, max_length=255)
    state_license_number: str = Field(min_length=2, max_length=100)
    school_code: str | None = Field(default=None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$")
    proprietor_name: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: EmailStr | None = None
    physical_address: str | None = None
    accreditation_status: str = Field(default="Active", pattern="^(Active|Probation|Suspended)$")
    manager_first_name: str = Field(default="School", min_length=1, max_length=100)
    manager_last_name: str = Field(default="Administrator", min_length=1, max_length=100)
    manager_email: EmailStr
    manager_password: str = Field(min_length=8, max_length=256)
    streams: list[str] = Field(default_factory=lambda: ["A"], min_length=1, max_length=12)


class StateSchoolUpdate(BaseModel):
    # Public school identity only; tenant-private finance fields are forbidden.
    model_config = ConfigDict(extra="forbid")

    school_name: str | None = Field(default=None, min_length=2, max_length=255)
    state_license_number: str | None = Field(default=None, min_length=2, max_length=100)
    school_code: str | None = Field(default=None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$")
    proprietor_name: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: EmailStr | None = None
    physical_address: str | None = None
    accreditation_status: str | None = Field(default=None, pattern="^(Active|Probation|Suspended)$")


class SchoolProfileUpdate(BaseModel):
    school_name: str | None = Field(default=None, min_length=2, max_length=255)
    proprietor_name: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: EmailStr | None = None
    physical_address: str | None = None
    billing_contact_name: str | None = Field(default=None, max_length=255)
    billing_phone: str | None = Field(default=None, max_length=50)
    billing_email: EmailStr | None = None
    billing_address: str | None = None
    billing_notes: str | None = None


class RollSequenceUpdate(BaseModel):
    next_value: int = Field(ge=1)


# --- Attendance ---
class AttendanceEntry(BaseModel):
    student_id: int
    status: str = Field(pattern="^(Present|Absent|Late|Excused)$")


class AttendanceBulkRequest(BaseModel):
    date: dt.date
    class_id: int
    entries: list[AttendanceEntry]
    # Refinement 3: teachers must address their own (subject, period) slot;
    # optional for managers, who keep whole-class authority.
    subject_id: int | None = None
    period_number: int | None = Field(default=None, ge=1, le=8)


class AttendanceSubmitRequest(BaseModel):
    date: dt.date | None = None


# --- Grades ---
class GradeEntry(BaseModel):
    student_id: int
    numeric_score: float = Field(ge=0, le=100)


class GradeBulkRequest(BaseModel):
    class_id: int
    subject_id: int
    academic_year_id: int
    exam_name: str = Field(min_length=1, max_length=150)
    entries: list[GradeEntry]


class PublishRequest(BaseModel):
    class_id: int
    subject_id: int
    academic_year_id: int
    exam_name: str


# --- Billing (tenant-private) ---
class TuitionRateCreate(BaseModel):
    class_level: str
    base_tuition_amount: float = Field(gt=0)
    billing_cycle: str = Field(default="Termly", pattern="^(Termly|Monthly|Annual)$")


class TuitionRateUpdate(BaseModel):
    base_tuition_amount: float | None = Field(default=None, gt=0)
    billing_cycle: str | None = Field(default=None, pattern="^(Termly|Monthly|Annual)$")
    class_level: str | None = None


class InvoiceCreate(BaseModel):
    student_id: int
    description: str = Field(min_length=1, max_length=255)
    amount_due: float = Field(ge=0)
    due_date: dt.date | None = None


class InvoiceUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=255)
    amount_due: float | None = Field(default=None, ge=0)
    due_date: dt.date | None = None


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_method: str = Field(pattern="^(Cash|Bank_Transfer|Mobile_Money|Card)$")
    reference_number: str | None = Field(default=None, max_length=100)


class PaymentUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    payment_method: str | None = Field(default=None, pattern="^(Cash|Bank_Transfer|Mobile_Money|Card)$")
    reference_number: str | None = Field(default=None, max_length=100)


# ===========================================================================
# Module 1 — Teacher absence & substitution engine
# ===========================================================================


class AbsenceCreate(BaseModel):
    teacher_id: int
    absence_date: dt.date | None = None  # defaults to today (platform tz)
    reason: str | None = Field(default=None, max_length=500)


class SubstitutionConfirm(BaseModel):
    absence_id: int
    period_number: int
    class_id: int
    substitute_teacher_id: int


# --- Timetable ---


class TimetableSlotRead(BaseModel):
    id: int
    class_id: int
    class_label: str | None = None
    subject_name: str | None = None
    teacher_id: int
    teacher_name: str | None = None
    day_of_week: int
    period_number: int


# ===========================================================================
# Module 2 — Syllabus completion tracker
# ===========================================================================


class SyllabusPlanCreate(BaseModel):
    class_id: int
    subject_id: int
    term: str = Field(default="Term 1", max_length=50)
    total_units: int = Field(gt=0, le=500)
    midterm_target_pct: float = Field(default=45, ge=0, le=100)
    final_target_pct: float = Field(default=100, ge=0, le=100)
    term_start: dt.date | None = None
    midterm_date: dt.date | None = None
    term_end: dt.date | None = None


class SyllabusBenchmarkUpdate(BaseModel):
    midterm_target_pct: float | None = Field(default=None, ge=0, le=100)
    final_target_pct: float | None = Field(default=None, ge=0, le=100)
    midterm_date: dt.date | None = None
    term_start: dt.date | None = None
    term_end: dt.date | None = None


class SyllabusProgressCreate(BaseModel):
    entry_date: dt.date | None = None  # defaults to today
    units_after: int = Field(ge=0, le=500)
    note: str | None = Field(default=None, max_length=300)


class SyllabusPlanUpdate(BaseModel):
    """Full manager edit of a pacing plan (all fields optional)."""

    term: str | None = Field(default=None, max_length=50)
    total_units: int | None = Field(default=None, gt=0, le=500)
    midterm_target_pct: float | None = Field(default=None, ge=0, le=100)
    final_target_pct: float | None = Field(default=None, ge=0, le=100)
    term_start: dt.date | None = None
    midterm_date: dt.date | None = None
    term_end: dt.date | None = None


class SyllabusTopicCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    code: str | None = Field(default=None, max_length=30)
    position: int | None = Field(default=None, ge=1, le=999)


class SyllabusTopicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    code: str | None = Field(default=None, max_length=30)
    position: int | None = Field(default=None, ge=1, le=999)


class SyllabusLogCoveredRequest(BaseModel):
    """'Log Topic Covered' modal payload: the ticked topic IDs."""

    topic_ids: list[int] = Field(min_length=1)
    entry_date: dt.date | None = None


class SyllabusUndoCoveredRequest(BaseModel):
    topic_ids: list[int] = Field(min_length=1)


# --- Refinement 3: subject-restricted roster marking ---


class TeacherRosterSave(BaseModel):
    class_id: int
    subject_id: int
    period_number: int = Field(ge=1, le=8)
    date: dt.date | None = None
    entries: list[AttendanceEntry]


# ===========================================================================
# Module 4 — Encrypted backups (state-admin only)
# ===========================================================================


class BackupRunRequest(BaseModel):
    kind: str = Field(default="auto", pattern="^(auto|full_snapshot|json_delta)$")


# ===========================================================================
# Module 5 — Biometric hardware management (WebAuthn)
# ===========================================================================


class BiometricEnrollOptionsRequest(BaseModel):
    owner_type: str = Field(pattern="^(student|staff)$")
    owner_id: int
    method: str = Field(default="fingerprint", pattern="^(fingerprint|smartcard|platform|usb_key|simulated)$")


class BiometricEnrollVerifyRequest(BaseModel):
    owner_type: str = Field(pattern="^(student|staff)$")
    owner_id: int
    method: str = Field(default="fingerprint", pattern="^(fingerprint|smartcard|platform|usb_key|simulated)$")
    credential_id: str = Field(min_length=8, max_length=512)
    client_data_b64: str
    attestation_object_b64: str
    transports: list[str] = Field(default_factory=list)
    expected_challenge: str


class BiometricVerifyOptionsRequest(BaseModel):
    purpose: str = Field(pattern="^(exam_hall_entry|staff_attendance|enrollment_check)$")
    owner_type: str = Field(pattern="^(student|staff)$")
    identifier: str = Field(min_length=1, max_length=255)


class BiometricVerifyCompleteRequest(BaseModel):
    purpose: str = Field(pattern="^(exam_hall_entry|staff_attendance|enrollment_check)$")
    owner_type: str = Field(pattern="^(student|staff)$")
    owner_id: int
    credential_id: str = Field(min_length=8, max_length=512)
    client_data_b64: str
    authenticator_data_b64: str
    signature_b64: str
    expected_challenge: str

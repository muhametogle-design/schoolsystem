"""Pydantic request/response contracts."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# --- Auth ---
class LoginRequest(BaseModel):
    """Email + password (managers/state) or Staff ID + PIN (teaching staff).

    Exactly one identifier is required; ``password`` doubles as the PIN for
    staff-ID sign-ins.
    """

    email: EmailStr | None = None
    staff_id: str | None = Field(default=None, min_length=2, max_length=30)
    password: str

    @model_validator(mode="after")
    def _one_identifier(self):
        if not self.email and not self.staff_id:
            raise ValueError("Provide an email address or a staff ID")
        return self


class UserInfo(BaseModel):
    id: int
    email: str
    role: str
    school_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    school_name: str | None = None


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


# --- Syllabus Completion Module (manager-owned CRUD) ---
class SyllabusTopicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    unit_code: str | None = Field(default=None, max_length=30)
    sort_order: int = Field(default=0, ge=0)


class SyllabusTopicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    unit_code: str | None = Field(default=None, max_length=30)
    sort_order: int | None = Field(default=None, ge=0)
    is_covered: bool | None = None


class SyllabusPlanCreate(BaseModel):
    class_id: int
    subject_id: int
    term_name: str = Field(default="Term 1", pattern="^Term [1-3]$")
    target_completion_pct: int = Field(default=100, ge=0, le=100)
    term_deadline: dt.date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    topics: list[SyllabusTopicCreate] = Field(default_factory=list, max_length=200)


class SyllabusPlanUpdate(BaseModel):
    term_name: str | None = Field(default=None, pattern="^Term [1-3]$")
    target_completion_pct: int | None = Field(default=None, ge=0, le=100)
    term_deadline: dt.date | None = None
    clear_term_deadline: bool = False
    progress_override_pct: int | None = Field(default=None, ge=0, le=100)
    clear_progress_override: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class TopicsCoveredRequest(BaseModel):
    """'Log Topic Covered' modal payload — bulk tick/untick curriculum units."""

    topic_ids: list[int] = Field(min_length=1, max_length=200)
    covered: bool = True


# --- Role-gated media management ---
class PhotoUploadRequest(BaseModel):
    """Base64 data-URL image (or null to remove). Manager/admin only."""

    photo: str | None = None

    @field_validator("photo")
    @classmethod
    def _validate_photo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("data:image/"):
            raise ValueError("photo must be a data:image/* URL")
        if len(value) > 900_000:  # ~650 KB binary — keeps the demo DB portable
            raise ValueError("photo exceeds the 650 KB upload limit")
        return value


# --- Design & layout configuration (Push Live payload) ---
class UiConfigPayload(BaseModel):
    accent: str | None = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")
    font: str | None = Field(default=None, pattern="^(sans|serif|mono)$")
    blocks: dict[str, bool] = Field(default_factory=dict)

    @field_validator("blocks")
    @classmethod
    def _validate_blocks(cls, value: dict[str, bool]) -> dict[str, bool]:
        allowed = {"profileCard", "academicOverview", "attendanceSummary", "biometricsBadge"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"Unknown dashboard blocks: {sorted(unknown)}")
        return value

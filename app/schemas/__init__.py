"""Pydantic request/response contracts."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
    enrollment_year: str = Field(default="2026", pattern="^[0-9]{4}$")


class StudentRead(BaseModel):
    id: int
    school_id: int
    national_student_id: str
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


# --- Classes / subjects ---
class ClassCreate(BaseModel):
    class_level: str
    class_stream: str
    room_number: str | None = None


class SubjectCreate(BaseModel):
    subject_code: str
    subject_name: str
    class_level: str


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


class InvoiceCreate(BaseModel):
    student_id: int
    description: str
    amount_due: float = Field(ge=0)
    due_date: dt.date | None = None


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_method: str = Field(pattern="^(Cash|Bank_Transfer|Mobile_Money|Card)$")
    reference_number: str | None = None

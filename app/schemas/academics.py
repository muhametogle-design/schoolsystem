"""Attendance / grade / course-section ingestion schemas."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

ATTENDANCE_STATUS = ("present", "absent", "late", "excused", "truant")


class AttendanceCreate(BaseModel):
    student_id: uuid.UUID
    course_section_id: Optional[uuid.UUID] = None
    attendance_date: date = Field(default_factory=date.today)
    status: str
    hours: float = Field(default=0, ge=0, le=24)

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in ATTENDANCE_STATUS:
            raise ValueError(f"status must be one of {ATTENDANCE_STATUS}")
        return v


class GradeCreate(BaseModel):
    course_section_id: uuid.UUID
    student_id: uuid.UUID
    exam_type: str = Field(default="continuous", pattern="^(continuous|midterm|final|mock)$")
    score: float = Field(ge=0, le=100)


class CourseSectionCreate(BaseModel):
    curriculum_id: uuid.UUID
    academic_year_id: uuid.UUID
    term_id: uuid.UUID
    classroom_id: uuid.UUID
    teacher_id: Optional[uuid.UUID] = None
    section_code: str = Field(min_length=1, max_length=40)
    weekly_contact_hours: float = Field(default=0, ge=0, le=80)
    schedule: list[dict[str, Any]] = Field(default_factory=list)
    state_code: str = Field(min_length=2, max_length=2)


class ValidatePayload(BaseModel):
    record_type: str = Field(pattern="^(attendance|grade|teacher|payroll|student)$")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=10_000)

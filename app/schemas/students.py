"""Student & mobility input/output schemas."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, EmailStr, field_validator


class StudentCreate(BaseModel):
    national_id: Optional[str] = Field(default=None, max_length=30)
    first_name: str = Field(min_length=1, max_length=120)
    middle_name: Optional[str] = Field(default=None, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    dob: date
    gender: str = Field(pattern="^(male|female|other)$")
    enrollment_kind: str = Field(default="k12", pattern="^(k12|tvet|higher_education|adult)$")
    current_major: Optional[str] = None
    current_grade_level: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    coordinates: Optional[tuple[float, float]] = None

    @field_validator("dob")
    @classmethod
    def dob_not_future(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("dob must be in the past")
        return v


class StudentOut(BaseModel):
    id: uuid.UUID
    ne_sid: str
    campus_id: uuid.UUID
    first_name: str
    last_name: str
    dob: date
    gender: str
    status: str
    matriculated_on: date

    model_config = {"from_attributes": True}


class MobilityCreate(BaseModel):
    to_campus_id: uuid.UUID
    from_enrollment_id: Optional[uuid.UUID] = None
    previous_mobility_id: Optional[uuid.UUID] = None
    edge_type: str = Field(default="horizontal_transfer", pattern="^(promotion|horizontal_transfer|upgrade|downgrade|re-entry)$")
    requested_on: date
    effective_on: Optional[date] = None
    notes: Optional[str] = None


class MobilityOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    from_campus_id: Optional[uuid.UUID]
    to_campus_id: uuid.UUID
    edge_type: str
    transfer_state: str
    effective_on: Optional[date]
    created_at: str

    model_config = {"from_attributes": True}

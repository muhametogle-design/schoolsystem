"""Teacher & payroll governance schemas."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class TeacherCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    dob: date
    national_id: Optional[str] = None
    is_civil_service: bool = True
    hire_date: Optional[date] = None


class TeacherCertificationCreate(BaseModel):
    cert_kind: str = Field(pattern="^(teaching_license|police_clearance|safety_certificate|special_education|other)$")
    cert_no: str = Field(min_length=3, max_length=120)
    issue_date: date
    expiry_date: Optional[date] = None
    next_renewal: Optional[date] = None


class PayrollProfileCreate(BaseModel):
    grade_tier: int = Field(ge=1, le=17)
    hardship_zone: Optional[str] = None
    regional_allowance: float = Field(default=0, ge=0)
    bank_code: Optional[str] = None
    bank_account_number: Optional[str] = None
    tin: str = Field(min_length=8, max_length=30)
    pension_rate: float = Field(default=7.5, ge=0, le=20)


class PayrollEntryCreate(BaseModel):
    teacher_id: uuid.UUID
    pay_period: str = Field(pattern=r"^\d{4}-\d{2}$")
    hours: float = Field(default=0, ge=0)
    base_pay: float = Field(default=0, ge=0)
    hardship_allowance: float = Field(default=0, ge=0)
    gross: float = Field(default=0, ge=0)
    pension_deduction: float = Field(default=0, ge=0)
    net: float = Field(default=0, ge=0)


class TeacherOut(BaseModel):
    id: uuid.UUID
    ne_tid: str
    campus_id: uuid.UUID
    first_name: str
    last_name: str
    employment_state: str
    hire_date: date

    model_config = {"from_attributes": True}

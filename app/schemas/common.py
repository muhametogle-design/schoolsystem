"""Shared Pydantic schemas."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

LOCK_ENTITY_TYPES = (
    "attendance",
    "exam_sheet",
    "grade",
    "payroll_entry",
    "teacher_profile",
    "classroom",
    "course_section",
    "student_record",
)


class ApiMessage(BaseModel):
    detail: str


class LockRequest(BaseModel):
    entity_type: str = Field(min_length=2)
    entity_id: uuid.UUID
    payload: Dict[str, Any]
    signature: bytes
    signature_scheme: str = Field(default="ed25519")
    key_version: int = Field(default=1, ge=1)

    @field_validator("entity_type")
    @classmethod
    def valid_entity(cls, v: str) -> str:
        if v not in LOCK_ENTITY_TYPES:
            raise ValueError(f"entity_type must be one of {LOCK_ENTITY_TYPES}")
        return v


class LockResponse(BaseModel):
    lock_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    payload_hash: str
    locked_by: uuid.UUID
    locked_at: str
    signature_scheme: str
    key_version: int


class UnlockRequest(BaseModel):
    force_with_state_key: bool = Field(default=False)
    signature: bytes
    signature_scheme: str = Field(default="ed25519")


class UnlockResponse(BaseModel):
    lock_id: uuid.UUID
    unlocked: bool
    note: str


class ValidationRuleStatus(BaseModel):
    rule: str
    passed: bool
    message: Optional[str] = None


class IngestionCell(BaseModel):
    field: str
    value: Any


class IngestionValidation(BaseModel):
    row_id: Optional[int] = None
    records: list[Any] = Field(default_factory=list)
    passed: bool
    rules: list[ValidationRuleStatus] = Field(default_factory=list)


class IngestionJobResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    accepted: int
    rejected: int
    message: str

"""Phase 1 Data Ingestion: format validation + persisting clerk submissions.

The service runs synchronous *format* validation rules on every cell, then
buffers accepted records and returns the rejected rows to the clerk. Real
writes are transactional and RLS-scoped to the clerk's campus.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.academics import Attendance, ExamSheet
from app.models.audit import RecordLock
from app.models.identity import AppUser
from app.models.registry import Student
from app.models.teachers import PayrollEntry, Teacher

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")
NATIONAL_ID_RE = re.compile(r"^[A-Z0-9-]{6,30}$")
ATTENDANCE_STATUS = {"present", "absent", "late", "excused", "truant"}
EXAM_TYPES = {"continuous", "midterm", "final", "mock"}


@dataclass
class ValidationResult:
    row_id: Optional[int]
    rules: List[Dict[str, Any]]
    passed: bool
    errors: List[str]


class IngestionError(ValueError):
    pass


def _digest_national_id(nid: str) -> str | None:
    if not nid:
        return None
    return hashlib.sha256(("neemis:nid:" + nid.upper()).encode()).hexdigest()


def validate_attendance_row(row: Dict[str, Any], row_id: Optional[int] = None) -> ValidationResult:
    errors: List[str] = []
    rules: List[Dict[str, Any]] = []
    status = str(row.get("status", "")).strip().lower()
    if status in ATTENDANCE_STATUS:
        rules.append({"rule": "attendance.status", "passed": True})
    else:
        rules.append({"rule": "attendance.status", "passed": False, "message": status})
        errors.append("status")

    d = row.get("attendance_date")
    if d is not None:
        try:
            date.fromisoformat(str(d))
            rules.append({"rule": "attendance.date", "passed": True})
        except ValueError:
            rules.append({"rule": "attendance.date", "passed": False, "message": str(d)})
            errors.append("attendance_date")

    try:
        hours = float(row.get("hours", 0))
        if 0 <= hours <= 24:
            rules.append({"rule": "hours.range", "passed": True})
        else:
            rules.append({"rule": "hours.range", "passed": False, "message": str(hours)})
            errors.append("hours")
    except (TypeError, ValueError):
        rules.append({"rule": "hours.range", "passed": False})
        errors.append("hours")

    student_id = str(row.get("student_id", ""))
    if _is_uuid(student_id):
        rules.append({"rule": "student_id.uuid", "passed": True})
    else:
        rules.append({"rule": "student_id.uuid", "passed": False, "message": student_id})
        errors.append("student_id")
    return ValidationResult(row_id, rules, not errors, errors)


def validate_grade_row(row: Dict[str, Any], row_id: Optional[int] = None) -> ValidationResult:
    errors: List[str] = []
    rules: List[Dict[str, Any]] = []
    exam_type = str(row.get("exam_type", "")).lower()
    if exam_type in EXAM_TYPES:
        rules.append({"rule": "grade.exam_type", "passed": True})
    else:
        rules.append({"rule": "grade.exam_type", "passed": False, "message": exam_type})
        errors.append("exam_type")

    try:
        score = float(row.get("score"))
        if 0 <= score <= 100:
            rules.append({"rule": "grade.score.range", "passed": True})
        else:
            rules.append({"rule": "grade.score.range", "passed": False, "message": str(score)})
            errors.append("score")
    except (TypeError, ValueError):
        rules.append({"rule": "grade.score.range", "passed": False})
        errors.append("score")
    for k in ("course_section_id", "student_id"):
        if not _is_uuid(str(row.get(k, ""))):
            errors.append(k)
            rules.append({"rule": f"{k}.uuid", "passed": False})
    return ValidationResult(row_id, rules, not errors, errors)


def validate_teacher_row(row: Dict[str, Any], row_id: Optional[int] = None) -> ValidationResult:
    errors: List[str] = []
    rules: List[Dict[str, Any]] = []
    for f in ("first_name", "last_name", "dob"):
        if str(row.get(f, "")).strip():
            rules.append({"rule": f"teacher.{f}.required", "passed": True})
        else:
            errors.append(f)
            rules.append({"rule": f"teacher.{f}.required", "passed": False})
    try:
        date.fromisoformat(str(row["dob"]))
        rules.append({"rule": "teacher.dob.format", "passed": True})
    except (ValueError, KeyError):
        errors.append("dob")
        rules.append({"rule": "teacher.dob.format", "passed": False})
    if row.get("national_id"):
        if NATIONAL_ID_RE.match(str(row["national_id"])):
            rules.append({"rule": "national_id.pattern", "passed": True})
        else:
            errors.append("national_id")
            rules.append({"rule": "national_id.pattern", "passed": False})
    return ValidationResult(row_id, rules, not errors, errors)


def validate_payroll_row(row: Dict[str, Any], row_id: Optional[int] = None) -> ValidationResult:
    errors: List[str] = []
    rules: List[Dict[str, Any]] = []
    if PERIOD_RE.match(str(row.get("pay_period", ""))):
        rules.append({"rule": "payroll.period", "passed": True})
    else:
        errors.append("pay_period")
        rules.append({"rule": "payroll.period", "passed": False})
    if not _is_uuid(str(row.get("teacher_id", ""))):
        errors.append("teacher_id")
        rules.append({"rule": "teacher_id.uuid", "passed": False})
    try:
        hours = float(row.get("hours", 0))
        if 0 <= hours <= 200:
            rules.append({"rule": "payroll.hours.range", "passed": True})
        else:
            errors.append("hours")
            rules.append({"rule": "payroll.hours.range", "passed": False, "message": str(hours)})
    except (TypeError, ValueError):
        errors.append("hours")
    return ValidationResult(row_id, rules, not errors, errors)


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def validate_batch(record_type: str, records: Iterable[Dict[str, Any]]) -> Tuple[List[ValidationResult], int]:
    validators = {
        "attendance": validate_attendance_row,
        "grade": validate_grade_row,
        "teacher": validate_teacher_row,
        "payroll": validate_payroll_row,
    }
    if record_type not in validators:
        raise IngestionError(f"Unknown record_type '{record_type}'")
    fn = validators[record_type]
    results: List[ValidationResult] = []
    for idx, row in enumerate(records, start=1):
        results.append(fn(row, row_id=idx))
    accepted = sum(1 for r in results if r.passed)
    return results, accepted


def persist_attendance(
    session: Session,
    *,
    campus_id: UUID,
    clerk_id: UUID,
    rows: Sequence[Dict[str, Any]],
) -> int:
    records: List[Attendance] = []
    for row in rows:
        records.append(
            Attendance(
                campus_id=campus_id,
                student_id=UUID(str(row["student_id"])),
                course_section_id=UUID(str(row["course_section_id"])) if row.get("course_section_id") else None,
                attendance_date=date.fromisoformat(str(row["attendance_date"])),
                status=str(row["status"]).lower(),
                hours=float(row.get("hours", 0)),
                clerk_id=clerk_id,
                source=row.get("source", "portal"),
            )
        )
    session.add_all(records)
    session.flush()
    return len(records)


def persist_grades(
    session: Session,
    *,
    campus_id: UUID,
    clerk_id: UUID,
    rows: Sequence[Dict[str, Any]],
) -> int:
    records: List[ExamSheet] = []
    for row in rows:
        records.append(
            ExamSheet(
                campus_id=campus_id,
                course_section_id=UUID(str(row["course_section_id"])),
                student_id=UUID(str(row["student_id"])),
                exam_type=str(row["exam_type"]).lower(),
                score=float(row["score"]),
                recorded_by=clerk_id,
            )
        )
    session.add_all(records)
    session.flush()
    return len(records)


def persist_teachers(
    session: Session,
    *,
    campus_id: UUID,
    clerk_id: UUID,
    rows: Sequence[Dict[str, Any]],
) -> int:
    records: List[Teacher] = []
    for row in rows:
        records.append(
            Teacher(
                campus_id=campus_id,
                first_name=row["first_name"],
                last_name=row["last_name"],
                dob=date.fromisoformat(str(row["dob"])),
                national_id_hash=_digest_national_id(row.get("national_id")),
                hire_date=date.fromisoformat(str(row.get("hire_date", date.today()))),
            )
        )
    session.add_all(records)
    session.flush()
    return len(records)


def persist_payroll(
    session: Session,
    *,
    campus_id: UUID,
    clerk_id: UUID,
    rows: Sequence[Dict[str, Any]],
) -> int:
    records: List[PayrollEntry] = []
    for row in rows:
        records.append(
            PayrollEntry(
                campus_id=campus_id,
                teacher_id=UUID(str(row["teacher_id"])),
                pay_period=str(row["pay_period"]),
                hours=float(row.get("hours", 0)),
                base_pay=float(row.get("base_pay", 0)),
                hardship_allowance=float(row.get("hardship_allowance", 0)),
                gross=float(row.get("gross", 0)),
                pension_deduction=float(row.get("pension_deduction", 0)),
                net=float(row.get("net", 0)),
                submitted_by=clerk_id,
            )
        )
    session.add_all(records)
    session.flush()
    return len(records)


def active_student_national_ids(session: Session, campus_id: UUID) -> set[str]:
    rows = (
        session.query(Student.national_id_hash)
        .filter(Student.campus_id == campus_id, Student.status == "active")
        .all()
    )
    return {r for (r,) in rows if r}

"""ORM model registry — importing this package registers every table."""

from __future__ import annotations

from app.models.academics import (
    ATTENDANCE_STATUSES,
    CLASS_LEVELS,
    CommunicationLog,
    DailySubmissionLog,
    ExamSubmissionEvent,
    LiveAttendance,
    SchoolClass,
    Student,
    StudentGrade,
    Subject,
)
from app.models.base import Base
from app.models.finance import PaymentTransaction, SecurityAuditLog, StudentInvoice, TuitionRate
from app.models.identity import AcademicYear, PrivateSchool, User

__all__ = [
    "Base",
    "ATTENDANCE_STATUSES",
    "CLASS_LEVELS",
    "AcademicYear",
    "CommunicationLog",
    "DailySubmissionLog",
    "ExamSubmissionEvent",
    "LiveAttendance",
    "PaymentTransaction",
    "PrivateSchool",
    "SchoolClass",
    "SecurityAuditLog",
    "Student",
    "StudentGrade",
    "StudentInvoice",
    "Subject",
    "TuitionRate",
    "User",
]

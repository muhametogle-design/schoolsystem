"""ORM model registry — importing this package registers every table."""

from __future__ import annotations

from app.models.academics import (
    ATTENDANCE_STATUSES,
    CLASS_LEVELS,
    FEE_STATUSES,
    CommunicationLog,
    DailySubmissionLog,
    ExamSubmissionEvent,
    LiveAttendance,
    SchoolClass,
    Student,
    StudentGrade,
    Subject,
    TeachingAssignment,
)
from app.models.base import Base
from app.models.curriculum import (
    SYLLABUS_TERMS,
    SchoolUiConfig,
    SyllabusPlan,
    SyllabusTopic,
)
from app.models.finance import (
    PAYMENT_STATUSES,
    PaymentTransaction,
    SecurityAuditLog,
    StudentInvoice,
    TuitionRate,
)
from app.models.identity import AcademicYear, PrivateSchool, SchoolRollSequence, User

__all__ = [
    "Base",
    "ATTENDANCE_STATUSES",
    "CLASS_LEVELS",
    "FEE_STATUSES",
    "PAYMENT_STATUSES",
    "SYLLABUS_TERMS",
    "AcademicYear",
    "CommunicationLog",
    "DailySubmissionLog",
    "ExamSubmissionEvent",
    "LiveAttendance",
    "PaymentTransaction",
    "PrivateSchool",
    "SchoolClass",
    "SchoolRollSequence",
    "SchoolUiConfig",
    "SecurityAuditLog",
    "Student",
    "StudentGrade",
    "StudentInvoice",
    "Subject",
    "SyllabusPlan",
    "SyllabusTopic",
    "TeachingAssignment",
    "TuitionRate",
    "User",
]

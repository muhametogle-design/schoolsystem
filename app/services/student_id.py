"""Secure staff IDs and State-administered school roll numbers.

Legacy NE-SID helpers are retained for API compatibility, but every new
student registration now receives a tenant roll number of the form
``[two-letter-school-code]-[sequence]`` such as ``NG-10023``. The sequence is
stored in ``school_roll_sequences`` and advanced atomically with enrollment.
"""

from __future__ import annotations

import random
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PrivateSchool, SchoolRollSequence, Student, User

_rng = random.SystemRandom()

# --- Legacy staff identifier schemes -------------------------------------- #
STUDENT_ID_PATTERN = "NE-SID-{year}-{alpha}{numeric}"
MANAGER_ID_PATTERN = "NE-MID-{year}-{alpha}{numeric}"
TEACHER_ID_PATTERN = "NE-TID-{year}-{alpha}{numeric}"

NE_SID_PREFIX = "NE-SID"  # re-exported for prior integrations
NE_MID_PREFIX = "NE-MID"
NE_TID_PREFIX = "NE-TID"

ALPHABET_LENGTH = 2
NUMERIC_LENGTH = 3
DEFAULT_ROLL_START = 10000

#: Which staff identifier scheme a role is issued.
STAFF_ID_PATTERN_BY_ROLE = {
    "school_manager": MANAGER_ID_PATTERN,
    "teacher": TEACHER_ID_PATTERN,
}


def _random_suffix() -> str:
    """2 secure uppercase letters followed by 3 secure digits, e.g. ``XY123``."""
    alpha = "".join(_rng.choices(string.ascii_uppercase, k=ALPHABET_LENGTH))
    numeric = "".join(_rng.choices(string.digits, k=NUMERIC_LENGTH))
    return f"{alpha}{numeric}"


def _issue_unique(
    database_session: Session,
    pattern: str,
    column,
    enrollment_year: str = "2026",
) -> str:
    """Issue a collision-checked code from ``pattern`` against a unique column."""
    while True:
        suffix = _random_suffix()
        candidate_id = pattern.format(
            year=enrollment_year,
            alpha=suffix[:ALPHABET_LENGTH],
            numeric=suffix[ALPHABET_LENGTH:],
        )
        collision_check = database_session.execute(select(column).where(column == candidate_id)).first()
        if not collision_check:
            return candidate_id


def generate_unique_national_student_id(
    database_session: Session, enrollment_year: str = "2026"
) -> str:
    """Issue a legacy collision-checked NE-SID tracking code.

    Kept for downstream integrations that explicitly ask for a legacy ID.
    Application registration should use :func:`generate_school_roll_number`.
    """
    return _issue_unique(
        database_session, STUDENT_ID_PATTERN, Student.national_student_id, enrollment_year
    )


def generate_school_roll_number(database_session: Session, school: PrivateSchool) -> str:
    """Allocate the next unique roll number for ``school``.

    ``SELECT .. FOR UPDATE`` serializes concurrent allocators in PostgreSQL;
    SQLite serializes its write transaction. A row is never re-used, including
    after a student becomes inactive or is moved to another class.
    """
    code = (school.school_code or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        raise ValueError("A school needs a unique two-letter school_code before student enrollment")

    # Lock the persisted allocator row before reading it. A plain Session.get
    # would leave two concurrent PostgreSQL registrations free to observe the
    # same next_value and issue the same roll number.
    sequence = (
        database_session.execute(
            select(SchoolRollSequence)
            .where(SchoolRollSequence.school_id == school.id)
            .with_for_update()
        )
        .scalar_one_or_none()
    )
    if sequence is None:
        sequence = SchoolRollSequence(school_id=school.id, next_value=DEFAULT_ROLL_START)
        database_session.add(sequence)

    value = int(sequence.next_value or DEFAULT_ROLL_START)
    while True:
        candidate = f"{code}-{value}"
        # Pending rows in this session may not be flushed, but the sequence
        # object's increment below protects repeated calls in one transaction.
        exists = database_session.execute(
            select(Student.id).where(Student.roll_number == candidate)
        ).first()
        value += 1
        if not exists:
            sequence.next_value = value
            return candidate


def set_school_roll_sequence(database_session: Session, school: PrivateSchool, next_value: int) -> SchoolRollSequence:
    """State Admin-only service to set the *next* roll number safely.

    It rejects values that would reuse an already issued number for the school.
    The API authorization check intentionally lives at the route boundary;
    keeping this function generic allows seed provisioning and repairs to use
    the same validation.
    """
    if next_value < 1:
        raise ValueError("next roll sequence must be positive")
    code = (school.school_code or "").upper()
    sequence = (
        database_session.execute(
            select(SchoolRollSequence)
            .where(SchoolRollSequence.school_id == school.id)
            .with_for_update()
        )
        .scalar_one_or_none()
    )
    already_used = database_session.execute(
        select(Student.id).where(Student.school_id == school.id, Student.roll_number == f"{code}-{next_value}")
    ).first()
    if already_used:
        raise ValueError("This roll number has already been issued and cannot be reused")
    if sequence is None:
        sequence = SchoolRollSequence(school_id=school.id, next_value=next_value)
        database_session.add(sequence)
    elif next_value < int(sequence.next_value):
        raise ValueError("The next roll sequence cannot move backwards")
    else:
        sequence.next_value = next_value
    return sequence


def generate_unique_staff_identifier(
    database_session: Session, role: str, enrollment_year: str = "2026"
) -> str:
    """Issue an un-duplicated NE-MID / NE-TID code for a staff profile."""
    pattern = STAFF_ID_PATTERN_BY_ROLE.get(role)
    if pattern is None:
        raise ValueError(f"No identifier scheme defined for role: {role!r}")
    return _issue_unique(database_session, pattern, User.staff_identifier, enrollment_year)

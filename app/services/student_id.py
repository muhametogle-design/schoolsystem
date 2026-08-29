"""IMPLEMENTATION PHASE 2 — Auto-generated secure national tracking IDs.

Two identifier families are issued:

  NE-SID  North-East Student Identification   NE-SID-2026-XY123
  NE-MID  North-East Manager Identification   NE-MID-2026-XY123
  NE-TID  North-East Teacher Identification   NE-TID-2026-XY123

Every code is 2 uppercase alphabetic characters + 3 digits, validated against
its owning table for absolute uniqueness before issuance, and uses a
cryptographically secure RNG (SystemRandom). Issued values are immutable
(see sql/002_security_firewall.sql).
"""

from __future__ import annotations

import random
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Student, User

_rng = random.SystemRandom()

# --- Identifier schemes --------------------------------------------------- #
STUDENT_ID_PATTERN = "NE-SID-{year}-{alpha}{numeric}"
MANAGER_ID_PATTERN = "NE-MID-{year}-{alpha}{numeric}"
TEACHER_ID_PATTERN = "NE-TID-{year}-{alpha}{numeric}"

NE_SID_PREFIX = "NE-SID"   # re-exported for the Pydantic + frontend layer
NE_MID_PREFIX = "NE-MID"
NE_TID_PREFIX = "NE-TID"

ALPHABET_LENGTH = 2
NUMERIC_LENGTH = 3

#: Which staff identifier scheme a role is issued.
STAFF_ID_PATTERN_BY_ROLE = {
    "school_manager": MANAGER_ID_PATTERN,
    "teacher": TEACHER_ID_PATTERN,
}


def _random_suffix() -> str:
    """2 secure uppercase letters followed by 3 secure digits, e.g. 'XY123'."""
    alpha = "".join(_rng.choices(string.ascii_uppercase, k=ALPHABET_LENGTH))
    numeric = "".join(_rng.choices(string.digits, k=NUMERIC_LENGTH))
    return f"{alpha}{numeric}"


def _issue_unique(
    database_session: Session,
    pattern: str,
    column,
    enrollment_year: str = "2026",
) -> str:
    """Issue a collision-checked code from `pattern` against a unique column."""
    while True:
        suffix = _random_suffix()
        candidate_id = pattern.format(
            year=enrollment_year,
            alpha=suffix[:ALPHABET_LENGTH],
            numeric=suffix[ALPHABET_LENGTH:],
        )
        collision_check = database_session.execute(
            select(column).where(column == candidate_id)
        ).first()
        if not collision_check:
            return candidate_id


def generate_unique_national_student_id(
    database_session: Session, enrollment_year: str = "2026"
) -> str:
    """Issues an un-duplicated NE-SID tracking code for a student profile.

    Format: NE-SID-2026-XY123
    """
    return _issue_unique(
        database_session, STUDENT_ID_PATTERN, Student.national_student_id, enrollment_year
    )


def generate_unique_staff_identifier(
    database_session: Session, role: str, enrollment_year: str = "2026"
) -> str:
    """Issues an un-duplicated NE-MID / NE-TID code for a staff profile.

    school_manager -> NE-MID-2026-XY123
    teacher        -> NE-TID-2026-XY123
    """
    pattern = STAFF_ID_PATTERN_BY_ROLE.get(role)
    if pattern is None:
        raise ValueError(f"No identifier scheme defined for role: {role!r}")
    return _issue_unique(database_session, pattern, User.staff_identifier, enrollment_year)

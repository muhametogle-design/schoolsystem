"""IMPLEMENTATION PHASE 2 — Auto-generated secure national student tracking ID.

Format Pattern: STU-2026-XY123
  * 2 uppercase alphabetic characters + 3 digits, validated against the
    students table for absolute uniqueness before issuance.
  * Uses a cryptographically secure RNG (SystemRandom).
  * The issued value is immutable (see sql/002_security_firewall.sql).
"""

from __future__ import annotations

import random
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Student

_rng = random.SystemRandom()

ID_PATTERN = "STU-{year}-{alpha}{numeric}"


def generate_unique_national_student_id(
    database_session: Session, enrollment_year: str = "2026"
) -> str:
    """Generates an un-duplicated, secure tracking code for student
    identification profiles. Format Pattern: STU-2026-XY123"""
    while True:
        alpha_suffix = "".join(_rng.choices(string.ascii_uppercase, k=2))
        numeric_suffix = "".join(_rng.choices(string.digits, k=3))
        candidate_id = ID_PATTERN.format(
            year=enrollment_year, alpha=alpha_suffix, numeric=numeric_suffix
        )

        # Validate uniqueness check
        collision_check = database_session.execute(
            select(Student.id).where(Student.national_student_id == candidate_id)
        ).first()
        if not collision_check:
            return candidate_id

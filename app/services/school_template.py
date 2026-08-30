"""Tenant provisioning and authoritative curriculum-assignment helpers.

A State Admin creates a school only once; this module lays down the complete
Class 1–12 structure, all mandatory subjects, a private billing rate scaffold,
a school roll sequence, and (when requested) a ready-to-edit teaching team.
"""

from __future__ import annotations

import itertools
import re
import secrets
import string
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    CLASS_LEVELS,
    PrivateSchool,
    SchoolClass,
    SchoolRollSequence,
    Subject,
    TeachingAssignment,
    TuitionRate,
    User,
)
from app.services.student_id import DEFAULT_ROLL_START, generate_unique_staff_identifier

# Mandated common core for every class, in the required presentation order.
CORE_SUBJECTS: tuple[tuple[str, str], ...] = (
    ("SOM", "Somali (Af-Somali)"),
    ("ARB", "Arabic"),
    ("ENG", "English"),
    ("MAT", "Mathematics"),
    ("ISL", "Islamic Studies"),
    ("PHY", "Physics"),
    ("CHE", "Chemistry"),
    ("BIO", "Biology"),
    ("HIS", "History"),
    ("GEO", "Geography"),
)


def _class_number(level: str) -> int:
    try:
        return int(level.rsplit(" ", 1)[-1])
    except (AttributeError, ValueError):
        return 999


def class_sort_key(klass: SchoolClass) -> tuple[int, str, int]:
    return (_class_number(klass.class_level), (klass.class_stream or "").casefold(), klass.id)


def mandatory_subjects_for_level(session: Session, school_id: int, class_level: str) -> list[Subject]:
    """Get subjects in curriculum order, with custom subjects after the core ten."""
    rows = (
        session.execute(
            select(Subject)
            .where(Subject.school_id == school_id, Subject.class_level == class_level)
        )
        .scalars()
        .all()
    )
    order = {name: index for index, (_, name) in enumerate(CORE_SUBJECTS)}
    return sorted(rows, key=lambda row: (order.get(row.subject_name, len(order)), row.subject_name.casefold(), row.id))


def _candidate_codes(name: str) -> list[str]:
    words = re.findall(r"[A-Za-z]+", name.upper())
    letters = "".join(words)
    values: list[str] = []
    if len(words) >= 2:
        values.append(words[0][0] + words[1][0])
    if len(letters) >= 2:
        values.append(letters[:2])
    # Distinct initial pairs add meaningful fallbacks before AA..ZZ allocation.
    if words:
        initials = "".join(word[0] for word in words)
        if len(initials) >= 2:
            values.append(initials[:2])
    return list(dict.fromkeys(value for value in values if len(value) == 2))


def allocate_school_code(session: Session, school_name: str, requested_code: str | None = None) -> str:
    """Return a globally unique uppercase two-letter school code.

    State Admin can request a code, but it must pass the same uniqueness rule
    as automatically allocated codes. Exhaustion is intentionally explicit;
    silently switching to a longer code would violate the roll-number format.
    """
    used = {
        value.upper()
        for (value,) in session.execute(select(PrivateSchool.school_code)).all()
        if value
    }
    requested = (requested_code or "").strip().upper()
    if requested:
        if len(requested) != 2 or not requested.isalpha():
            raise ValueError("school_code must be exactly two alphabetic letters")
        if requested in used:
            raise ValueError(f"School code {requested} is already in use")
        return requested
    for candidate in _candidate_codes(school_name):
        if candidate not in used:
            return candidate
    for first, second in itertools.product(string.ascii_uppercase, repeat=2):
        candidate = first + second
        if candidate not in used:
            return candidate
    raise ValueError("All two-letter school codes are in use")


def provision_school_template(
    session: Session,
    school: PrivateSchool,
    *,
    streams: Iterable[str] = ("A",),
    default_tuition_amount: float = 100.0,
) -> dict[str, int]:
    """Idempotently provision every structural tenant record for a school."""
    normalized_streams = list(dict.fromkeys(str(stream).strip() for stream in streams if str(stream).strip())) or ["A"]
    classes_created = 0
    subjects_created = 0
    rates_created = 0

    existing_classes = {
        (row.class_level, row.class_stream): row
        for row in session.execute(select(SchoolClass).where(SchoolClass.school_id == school.id)).scalars()
    }
    for level in CLASS_LEVELS:
        for stream in normalized_streams:
            if (level, stream) not in existing_classes:
                session.add(
                    SchoolClass(
                        school_id=school.id,
                        class_level=level,
                        class_stream=stream,
                        room_number=f"R-{_class_number(level)}{stream}",
                    )
                )
                classes_created += 1

    existing_subject_codes = {
        (row.subject_code, row.class_level)
        for row in session.execute(select(Subject).where(Subject.school_id == school.id)).scalars()
    }
    for level in CLASS_LEVELS:
        number = _class_number(level)
        for code, name in CORE_SUBJECTS:
            subject_code = f"{code}-{number:02d}"
            if (subject_code, level) not in existing_subject_codes:
                session.add(
                    Subject(
                        school_id=school.id,
                        subject_code=subject_code,
                        subject_name=name,
                        class_level=level,
                    )
                )
                subjects_created += 1

    existing_rates = {
        (row.class_level, row.billing_cycle)
        for row in session.execute(select(TuitionRate).where(TuitionRate.school_id == school.id)).scalars()
    }
    for level in CLASS_LEVELS:
        if (level, "Termly") not in existing_rates:
            session.add(
                TuitionRate(
                    school_id=school.id,
                    class_level=level,
                    base_tuition_amount=default_tuition_amount,
                    billing_cycle="Termly",
                )
            )
            rates_created += 1

    if session.get(SchoolRollSequence, school.id) is None:
        session.add(SchoolRollSequence(school_id=school.id, next_value=DEFAULT_ROLL_START))

    # Flush so callers can immediately create assignments from newly made rows.
    session.flush()
    return {
        "classes_created": classes_created,
        "subjects_created": subjects_created,
        "tuition_rates_created": rates_created,
    }


def create_template_teachers(session: Session, school: PrivateSchool, count: int = 8) -> list[User]:
    """Create editable initial faculty profiles for a newly provisioned school.

    The generated passwords are deliberately random and never returned. A
    school manager should edit each profile and set an actual initial password
    before staff use the account. This gives every template class/subject an
    explicit staff mapping immediately without shipping a shared password.
    """
    existing = (
        session.execute(
            select(User)
            .where(User.school_id == school.id, User.role == "teacher")
            .order_by(User.id)
        )
        .scalars()
        .all()
    )
    needed = max(0, count - len(existing))
    year = "2026"
    for position in range(len(existing) + 1, len(existing) + needed + 1):
        code = school.school_code.lower()
        existing.append(
            User(
                school_id=school.id,
                email=f"faculty{position}.{code}@school.local",
                password_hash=hash_password(secrets.token_urlsafe(24)),
                role="teacher",
                first_name=school.school_code,
                last_name=f"Faculty {position}",
                staff_identifier=generate_unique_staff_identifier(session, "teacher", year),
                designation="Template teacher — update profile",
                qualifications="Profile setup required",
                bio="Template faculty record created when this school was provisioned.",
                is_active=True,
            )
        )
    session.add_all(existing[-needed:] if needed else [])
    session.flush()
    return existing


def ensure_assignments_for_class(
    session: Session,
    school: PrivateSchool,
    klass: SchoolClass,
    *,
    fallback_teacher_id: int | None = None,
) -> int:
    """Create missing subject mappings for one class without overwriting staff."""
    subjects = mandatory_subjects_for_level(session, school.id, klass.class_level)
    existing = {
        subject_id
        for (subject_id,) in session.execute(
            select(TeachingAssignment.subject_id).where(
                TeachingAssignment.school_id == school.id,
                TeachingAssignment.class_id == klass.id,
            )
        ).all()
    }
    created = 0
    for subject in subjects:
        if subject.id not in existing:
            session.add(
                TeachingAssignment(
                    school_id=school.id,
                    class_id=klass.id,
                    subject_id=subject.id,
                    teacher_id=fallback_teacher_id,
                )
            )
            created += 1
    return created


def ensure_assignments_for_subject(
    session: Session,
    school: PrivateSchool,
    subject: Subject,
    *,
    fallback_teacher_id: int | None = None,
) -> int:
    """Add the newly created subject to every stream at its class level."""
    classes = (
        session.execute(
            select(SchoolClass).where(
                SchoolClass.school_id == school.id,
                SchoolClass.class_level == subject.class_level,
            )
        )
        .scalars()
        .all()
    )
    created = 0
    for klass in classes:
        exists = session.execute(
            select(TeachingAssignment.id).where(
                TeachingAssignment.school_id == school.id,
                TeachingAssignment.class_id == klass.id,
                TeachingAssignment.subject_id == subject.id,
            )
        ).first()
        if not exists:
            session.add(
                TeachingAssignment(
                    school_id=school.id,
                    class_id=klass.id,
                    subject_id=subject.id,
                    teacher_id=fallback_teacher_id,
                )
            )
            created += 1
    return created


def assign_complete_curriculum(
    session: Session,
    school: PrivateSchool,
    teachers: list[User],
    *,
    overwrite: bool = False,
) -> int:
    """Ensure every class-subject pair has a teacher and mapping.

    Teacher assignment rotates through the supplied team by core subject, so a
    teacher has a coherent subject portfolio across Class 1–12. Existing
    mappings are preserved unless ``overwrite`` is requested by seeding.
    """
    if not teachers:
        return 0
    teachers = [teacher for teacher in teachers if teacher.role == "teacher"]
    if not teachers:
        return 0

    classes = (
        session.execute(select(SchoolClass).where(SchoolClass.school_id == school.id))
        .scalars()
        .all()
    )
    subject_order = {name: index for index, (_, name) in enumerate(CORE_SUBJECTS)}
    changed = 0
    for klass in sorted(classes, key=class_sort_key):
        if not klass.class_teacher_id:
            klass.class_teacher_id = teachers[(_class_number(klass.class_level) - 1) % len(teachers)].id
        subjects = mandatory_subjects_for_level(session, school.id, klass.class_level)
        existing = {
            assignment.subject_id: assignment
            for assignment in session.execute(
                select(TeachingAssignment).where(
                    TeachingAssignment.school_id == school.id,
                    TeachingAssignment.class_id == klass.id,
                )
            ).scalars()
        }
        for position, subject in enumerate(subjects):
            teacher_index = subject_order.get(subject.subject_name, position) % len(teachers)
            teacher_id = teachers[teacher_index].id
            assignment = existing.get(subject.id)
            if assignment is None:
                session.add(
                    TeachingAssignment(
                        school_id=school.id,
                        class_id=klass.id,
                        subject_id=subject.id,
                        teacher_id=teacher_id,
                    )
                )
                changed += 1
            elif overwrite or assignment.teacher_id is None:
                if assignment.teacher_id != teacher_id:
                    assignment.teacher_id = teacher_id
                    changed += 1
    return changed

"""Operations-tier seed: timetable, syllabus plans, demo absence, biometric logs.

Called at the end of ``seed_data.seed()`` so every seeded school opens with:

* a full weekly timetable (Mon-Fri, 4 periods) built from the authoritative
  class/subject/teacher assignments;
* a Class 1-12 syllabus tracking plan per subject with audited progress
  checkpoints spanning the status spectrum (On Track / Ahead / Behind);
* at Nugaal High School: one absence logged for today with engine-confirmed
  coverage, plus one open absence at Ilays for a live panel demo;
* exam-hall-entry and staff-attendance biometric verification history.

Everything is deterministic (dedicated Random instance) so repeated seeds
produce identical demo estates.
"""

from __future__ import annotations

import datetime as dt
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PrivateSchool,
    SchoolClass,
    Student,
    Subject,
    SyllabusPlan,
    SyllabusProgressEntry,
    TeacherAbsence,
    TeachingAssignment,
    TimetableSlot,
    User,
)
from app.services.substitution import auto_assign_best

rng = random.Random(20260901)

PERIODS_PER_DAY = 4
DAYS_PER_WEEK = 5
WEEK_TOTAL_SLOTS = PERIODS_PER_DAY * DAYS_PER_WEEK

#: Deterministic progress spread so the tracker demo shows all three tags.
_PATTERN_AHEAD = {1, 4, 7}
_PATTERN_BEHIND = {3, 5, 9}


#: Extra named subject specialists added to each seeded school. The original
#: eight generalist profiles stay untouched (documented demo accounts); these
#: give the timetable enough teacher capacity to be physically consistent and
#: give the substitution engine real subject specialists to match.
SPECIALIST_PLAN: dict[str, int] = {
    "SOM": 4, "ARB": 4, "ENG": 4, "MAT": 4, "ISL": 3,
    "PHY": 3, "CHE": 3, "BIO": 3, "HIS": 3, "GEO": 3,
}
SPECIALIST_SUBJECT_KEYWORDS: dict[str, tuple[str, str]] = {
    "SOM": ("Somali Language", "B.Ed Somali Language - University of Hargeisa"),
    "ARB": ("Arabic Language", "B.Ed Arabic Language - Mogadishu University"),
    "ENG": ("English Language", "B.A English - East Africa University"),
    "MAT": ("Mathematics", "B.Sc Mathematics, PGDE - Amoud University"),
    "ISL": ("Islamic Studies", "B.A Islamic Studies - Ma'ahad Islamic Institute"),
    "PHY": ("Physics", "B.Sc Physics, PGDE - University of Hargeisa"),
    "CHE": ("Chemistry", "B.Sc Chemistry, PGDE - Amoud University"),
    "BIO": ("Biology", "B.Sc Biology, PGDE - University of Hargeisa"),
    "HIS": ("History", "B.Ed History - University of Hargeisa"),
    "GEO": ("Geography", "B.Ed Geography - Puntland State University"),
}
#: Keywords that pull an existing generalist profile into a subject pool.
GENERALIST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "SOM": ("somali", "languages"),
    "ARB": ("arabic", "islamic"),
    "ENG": ("english", "languages"),
    "MAT": ("mathematic", "maths"),
    "ISL": ("islamic", "arabic"),
    "PHY": ("physics", "science"),
    "CHE": ("chemistry", "science"),
    "BIO": ("biology", "science"),
    "HIS": ("history", "social science", "humanities"),
    "GEO": ("geography", "social science", "humanities"),
}
SPECIALIST_NAMES = [
    ("Warsame", "Jama"), ("Nasteho", "Ali"), ("Cabdiraxmaan", "Nur"),
    ("Hodan", "Warsame"), ("Ismael", "Farah"), ("Ubah", "Hersi"),
    ("Siciid", "Adan"), ("Barwaqo", "Mohamed"), ("Xasan", "Gedi"),
    ("Roda", "Osman"), ("Axmed", "Kahin"), ("Sagal", "Nur"),
    ("Faarah", "Ibrahim"), ("Hamda", "Yusuf"), ("Dalsan", "Farah"),
    ("Rahma", "Diriye"), ("Ghanie", "Abdi"), ("Zumra", "Adan"),
    ("Bile", "Hersi"), ("Idil", "Jama"), ("Kaysar", "Mohamed"),
    ("Shukri", "Ali"), ("Wali", "Nur"), ("Ardo", "Gedi"),
    ("Yasin", "Osman"),
]


def seed_operations(session: Session) -> None:
    schools = session.execute(select(PrivateSchool)).scalars().all()
    today = dt.date.today()
    for school in schools:
        classes = session.execute(
            select(SchoolClass).where(SchoolClass.school_id == school.id)
        ).scalars().all()
        classes.sort(key=lambda klass: (int(klass.class_level.split()[-1]), klass.class_stream, klass.id))

        specialists = _ensure_specialists(session, school)
        _rebalance_assignments(session, school, specialists)
        _seed_timetable(session, school, classes)
        _seed_syllabus(session, school, classes, today)

    session.flush()

    # Live substitution-engine demo: NG has a covered absence (engine already
    # confirmed the coverage); IL has an open one for the panel walkthrough.
    ng = next((s for s in schools if s.school_code == "NG"), None)
    il = next((s for s in schools if s.school_code == "IL"), None)
    if ng:
        _seed_absence(session, ng, today, teacher_index=2, auto=True,
                      reason="Medical leave — approved by manager")
    if il:
        _seed_absence(session, il, today, teacher_index=4, auto=False,
                      reason="Official examination workshop (state board)")

    for school in schools:
        _seed_biometric_history(session, school, today)

    # NOTE: the change-capture log is intentionally NOT trimmed here. JSON
    # deltas chain from the last snapshot of ANY kind (see backup.py), so the
    # first midnight delta exports only what changed after the full snapshot.
    session.flush()


# ---------------------------------------------------------------------------
# Specialist staff & assignment rebalancing
# ---------------------------------------------------------------------------


def _ensure_specialists(session: Session, school: PrivateSchool) -> dict[str, list[User]]:
    """Idempotently create the subject-specialist wave for one school."""
    from app.core.security import hash_password
    from app.services.student_id import generate_unique_staff_identifier

    existing = session.execute(
        select(User).where(User.school_id == school.id, User.role == "teacher").order_by(User.id)
    ).scalars().all()
    domain_map = {
        "IL": "ilays.edu.so", "MY": "museyusuf.edu.so", "NG": "nugaal.edu.so",
        "AQ": "alqalam.edu.so", "LB": "lbss.edu.so",
    }
    domain = domain_map.get(school.school_code, f"{school.school_code.lower()}.edu.so")

    pool: dict[str, list[User]] = {}
    name_index = 0
    year = str(dt.date.today().year)
    for code, count in SPECIALIST_PLAN.items():
        designation, qualifications = SPECIALIST_SUBJECT_KEYWORDS[code]
        specialists = [u for u in existing if u.designation == f"{designation} Specialist"]
        while len(specialists) < count:
            first, last = SPECIALIST_NAMES[name_index % len(SPECIALIST_NAMES)]
            name_index += 1
            number = len(existing) + name_index
            user = User(
                school_id=school.id,
                email=f"{code.lower()}.specialist{number}@{domain}",
                password_hash=hash_password("Teach@2026"),
                role="teacher",
                first_name=first,
                last_name=last,
                staff_identifier=generate_unique_staff_identifier(session, "teacher", year),
                phone=f"+252-63-{4400000 + school.id * 1000 + number}",
                qualifications=qualifications,
                designation=f"{designation} Specialist",
                bio=f"{designation} specialist teacher at {school.school_name}.",
                is_active=True,
            )
            session.add(user)
            session.flush()
            specialists.append(user)
        pool[code] = specialists

    # Multi-subject generalists (the original eight) join every pool their
    # designation/qualifications mention, e.g. "Somali and History Teacher".
    for user in existing:
        haystack = " ".join(filter(None, [user.designation, user.qualifications])).casefold()
        for code, keywords in GENERALIST_KEYWORDS.items():
            if any(keyword in haystack for keyword in keywords):
                pool.setdefault(code, []).append(user)
    session.flush()
    return pool


def _rebalance_assignments(session: Session, school: PrivateSchool, pool: dict[str, list[User]]) -> None:
    """Spread teaching assignments across the widened staff, load-balanced.

    Original generalists stay in every subject pool, so the documented demo
    accounts keep classes; specialists absorb the surplus. Every assignment
    lands on the least-loaded teacher of that subject's pool.
    """
    from app.models import Subject, TeachingAssignment

    load: dict[int, int] = {}
    rows = session.execute(
        select(TeachingAssignment, Subject)
        .join(Subject, TeachingAssignment.subject_id == Subject.id)
        .where(TeachingAssignment.school_id == school.id)
        .order_by(Subject.class_level, Subject.subject_code, TeachingAssignment.id)
    ).all()
    for assignment, subject in rows:
        load[assignment.teacher_id] = load.get(assignment.teacher_id, 0) + 1

    for assignment, subject in rows:
        candidates = pool.get(subject.subject_code, [])
        if not candidates:
            continue
        choice = min(candidates, key=lambda user: (load.get(user.id, 0), user.id))
        if choice.id != assignment.teacher_id:
            load[assignment.teacher_id] = load.get(assignment.teacher_id, 0) - 1
            assignment.teacher_id = choice.id
            load[choice.id] = load.get(choice.id, 0) + 1
    session.flush()


# ---------------------------------------------------------------------------
# Timetable
# ---------------------------------------------------------------------------


def _seed_timetable(session: Session, school: PrivateSchool, classes: list[SchoolClass]) -> None:
    """Conflict-free weekly timetable built from the authoritative assignments.

    Two placement passes per class:

    1. **Coverage pass** — every subject of the class is placed once, at the
       (day, period) pair where its assigned teacher is free; the scarcest
       teacher (fewest free periods left) is consumed first.
    2. **Double-period pass** — any period still empty takes an extra period
       of a subject whose teacher is free (standard double-period practice),
       so every class carries a full two-periods-per-day timetable.

    Classes alternate the morning pair (periods 1,3) and the afternoon pair
    (2,4), halving concurrent demand. The two uniqueness rules of
    ``timetable_slots`` hold by construction.
    """
    busy_teacher: set[tuple[int, int, int]] = set()  # (teacher_id, day, period)
    free_left: dict[int, int] = {}  # teacher_id -> free periods left this week

    for class_index, klass in enumerate(classes):
        assignments = session.execute(
            select(TeachingAssignment, Subject)
            .join(Subject, TeachingAssignment.subject_id == Subject.id)
            .where(TeachingAssignment.class_id == klass.id)
        ).all()
        if not assignments:
            continue
        assignments.sort(key=lambda row: (row[1].subject_code, row[1].id))
        rotation = [(int(a.teacher_id), int(s.id), s.subject_code) for a, s in assignments]
        for teacher_id, _subject_id, _code in rotation:
            free_left.setdefault(teacher_id, WEEK_TOTAL_SLOTS)

        pattern = (1, 3) if class_index % 2 == 0 else (2, 4)
        combos = [(day, period) for day in range(DAYS_PER_WEEK) for period in pattern]
        filled: set[tuple[int, int]] = set()

        # Pass 1 — cover every subject once, scarcest teacher first.
        for teacher_id, subject_id, code in sorted(
            rotation, key=lambda item: (free_left.get(item[0], 0), item[2])
        ):
            for day, period in combos:
                if (day, period) in filled:
                    continue
                if (teacher_id, day, period) in busy_teacher or free_left.get(teacher_id, 0) <= 0:
                    continue
                session.add(
                    TimetableSlot(
                        school_id=school.id,
                        class_id=klass.id,
                        subject_id=subject_id,
                        teacher_id=teacher_id,
                        day_of_week=day,
                        period_number=period,
                    )
                )
                busy_teacher.add((teacher_id, day, period))
                free_left[teacher_id] -= 1
                filled.add((day, period))
                break

        # Pass 2 — double periods for any remaining empty class periods.
        for index, (day, period) in enumerate(combos):
            if (day, period) in filled:
                continue
            candidates = [
                (teacher_id, subject_id)
                for teacher_id, subject_id, _code in rotation
                if (teacher_id, day, period) not in busy_teacher and free_left.get(teacher_id, 0) > 0
            ]
            if not candidates:
                continue
            teacher_id, subject_id = candidates[index % len(candidates)]
            session.add(
                TimetableSlot(
                    school_id=school.id,
                    class_id=klass.id,
                    subject_id=subject_id,
                    teacher_id=teacher_id,
                    day_of_week=day,
                    period_number=period,
                )
            )
            busy_teacher.add((teacher_id, day, period))
            free_left[teacher_id] -= 1


# ---------------------------------------------------------------------------
# Syllabus plans
# ---------------------------------------------------------------------------


def _seed_syllabus(
    session: Session, school: PrivateSchool, classes: list[SchoolClass], today: dt.date
) -> None:
    term_start = today - dt.timedelta(days=45)
    midterm = today + dt.timedelta(days=15)
    term_end = today + dt.timedelta(days=75)

    for klass in classes:
        class_number = int(klass.class_level.split()[-1])
        assignments = session.execute(
            select(TeachingAssignment, Subject)
            .join(Subject, TeachingAssignment.subject_id == Subject.id)
            .where(TeachingAssignment.class_id == klass.id)
        ).all()
        assignments.sort(key=lambda row: (row[1].subject_code, row[1].id))

        for assignment_index, (assignment, subject) in enumerate(assignments):
            total_units = 12 + (class_number % 4) * 2 + (assignment_index % 3)
            plan = SyllabusPlan(
                school_id=school.id,
                class_id=klass.id,
                subject_id=subject.id,
                term="Term 1",
                total_units=total_units,
                midterm_target_pct=45,
                final_target_pct=100,
                term_start=term_start,
                midterm_date=midterm,
                term_end=term_end,
                created_by=assignment.teacher_id,
            )
            session.add(plan)
            session.flush()

            # Deterministic checkpoint history across the three status bands.
            seed_value = (class_number * 7 + assignment_index * 3) % 10
            elapsed = (today - term_start).days
            expected_units = round(total_units * min(1.0, max(0.0, elapsed / 120.0)))
            if seed_value in _PATTERN_AHEAD:
                final_units = min(total_units, expected_units + max(2, total_units // 6))
            elif seed_value in _PATTERN_BEHIND:
                final_units = max(0, int(expected_units * 0.7))
            else:
                final_units = expected_units

            checkpoints = [
                (term_start + dt.timedelta(days=15), round(final_units * 0.25)),
                (term_start + dt.timedelta(days=30), round(final_units * 0.6)),
                (today, final_units),
            ]
            for entry_date, units in checkpoints:
                if units < 0:
                    continue
                session.add(
                    SyllabusProgressEntry(
                        plan_id=plan.id,
                        school_id=school.id,
                        entry_date=entry_date,
                        units_after=units,
                        note=None,
                        recorded_by=assignment.teacher_id,
                    )
                )


# ---------------------------------------------------------------------------
# Demo absences (substitution engine)
# ---------------------------------------------------------------------------


def _seed_absence(
    session: Session,
    school: PrivateSchool,
    today: dt.date,
    *,
    teacher_index: int,
    auto: bool,
    reason: str,
) -> None:
    manager = session.execute(
        select(User).where(User.school_id == school.id, User.role == "school_manager")
    ).scalar_one_or_none()
    teachers = session.execute(
        select(User).where(User.school_id == school.id, User.role == "teacher").order_by(User.id)
    ).scalars().all()
    if not teachers or len(teachers) <= teacher_index:
        return

    # Pick a teacher who actually teaches today (deterministic scan).
    teacher = teachers[teacher_index]
    if not session.execute(
        select(TimetableSlot.id).where(
            TimetableSlot.school_id == school.id,
            TimetableSlot.teacher_id == teacher.id,
            TimetableSlot.day_of_week == today.weekday(),
        )
    ).first():
        return

    absence = TeacherAbsence(
        school_id=school.id,
        teacher_id=teacher.id,
        absence_date=today,
        reason=reason,
        status="logged",
        logged_by=manager.id if manager else None,
    )
    session.add(absence)
    session.flush()

    if auto:
        auto_assign_best(session, absence, assigned_by=manager.id if manager else None)
    session.flush()


# ---------------------------------------------------------------------------
# Biometric verification history (exam hall + staff attendance)
# ---------------------------------------------------------------------------


def _seed_biometric_history(session: Session, school: PrivateSchool, today: dt.date) -> None:
    from app.models import BiometricVerificationLog

    students = session.execute(
        select(Student)
        .join(SchoolClass, Student.current_class_id == SchoolClass.id)
        .where(Student.school_id == school.id, SchoolClass.class_level.in_(("Class 9", "Class 10")))
        .order_by(Student.roll_number)
        .limit(8)
    ).scalars().all()
    teachers = session.execute(
        select(User).where(User.school_id == school.id, User.role == "teacher").order_by(User.id).limit(3)
    ).scalars().all()

    for index, student in enumerate(students):
        hour = 8 + index // 8
        session.add(
            BiometricVerificationLog(
                school_id=school.id,
                owner_type="student",
                owner_id=student.id,
                purpose="exam_hall_entry",
                result="success" if index != 5 else "failed",
                credential_id=None,
                person_label=f"{student.first_name} {student.last_name}",
                detail=(
                    "Legacy handheld scanner #A2"
                    if index != 5
                    else "Legacy handheld scanner #A2 — fingerprint mismatch, invigilator checked ID"
                ),
                verified_at=dt.datetime.combine(today, dt.time(hour, 30 + index * 3)),
                operated_by=None,
            )
        )

    for index, teacher in enumerate(teachers):
        session.add(
            BiometricVerificationLog(
                school_id=school.id,
                owner_type="staff",
                owner_id=teacher.id,
                purpose="staff_attendance",
                result="success",
                credential_id=None,
                person_label=f"{teacher.first_name} {teacher.last_name}",
                detail="Legacy wall-mounted reader (migrated history)",
                verified_at=dt.datetime.combine(today, dt.time(7, 40 + index * 5)),
                operated_by=None,
            )
        )

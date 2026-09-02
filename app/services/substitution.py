"""Module 1 — Teacher absence & substitution engine.

When an absence is logged, the engine projects the absent teacher's timetable
slots for that date and ranks available colleagues in real time:

1. **Hard filters** — same tenant, active account, not absent themselves, and
   free at the affected (day, period) per ``timetable_slots`` ("unassigned
   period slots").
2. **Scoring** — subject specialization, department/qualification keywords,
   and subject-group affinity, with a light load-balancing tiebreaker.

The scorer returns machine-readable ``reasons`` so managers can audit *why*
every candidate was recommended.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    SchoolClass,
    SubstitutionAssignment,
    Subject,
    TeacherAbsence,
    TeachingAssignment,
    TimetableSlot,
    User,
)

WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Subject code -> keywords matched (case-insensitive) against a teacher's
# qualifications and designation for the department-qualification signal.
SUBJECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "SOM": ("somali", "af-somali", "languages"),
    "ARB": ("arabic", "islamic studies", "languages"),
    "ENG": ("english", "languages"),
    "MAT": ("mathematic", "maths", "quantitative"),
    "ISL": ("islamic", "arabic"),
    "PHY": ("physics", "science"),
    "CHE": ("chemistry", "science"),
    "BIO": ("biology", "science"),
    "HIS": ("history", "social science", "humanities"),
    "GEO": ("geography", "social science", "humanities"),
}

# Subject codes grouped into departments for the softer affinity signal.
SUBJECT_GROUPS: dict[str, str] = {
    "SOM": "languages",
    "ARB": "languages",
    "ENG": "languages",
    "ISL": "humanities",
    "HIS": "humanities",
    "GEO": "humanities",
    "MAT": "sciences",
    "PHY": "sciences",
    "CHE": "sciences",
    "BIO": "sciences",
}

SCORE_EXACT_SUBJECT = 50
SCORE_QUALIFICATION = 25
SCORE_DEPARTMENT = 10


@dataclass
class Candidate:
    """One ranked substitute candidate for one absent slot."""

    teacher_id: int
    full_name: str
    staff_identifier: str | None
    designation: str | None
    qualifications: str | None
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    busy_periods: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "teacher_id": self.teacher_id,
            "full_name": self.full_name,
            "staff_identifier": self.staff_identifier,
            "designation": self.designation,
            "qualifications": self.qualifications,
            "score": self.score,
            "reasons": self.reasons,
            "busy_periods": self.busy_periods,
        }


def _display_name(user: User) -> str:
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or user.email


def _teacher_subject_map(db: Session, school_id: int) -> dict[int, set[int]]:
    """teacher_id -> set of subject_ids they currently teach (specialization)."""
    rows = db.execute(
        select(TeachingAssignment.teacher_id, TeachingAssignment.subject_id).where(
            TeachingAssignment.school_id == school_id
        )
    ).all()
    mapping: dict[int, set[int]] = {}
    for teacher_id, subject_id in rows:
        mapping.setdefault(int(teacher_id), set()).add(int(subject_id))
    return mapping


def _teacher_day_busy(db: Session, school_id: int, day_of_week: int) -> dict[int, set[int]]:
    """teacher_id -> set of period numbers they occupy on ``day_of_week``."""
    rows = db.execute(
        select(TimetableSlot.teacher_id, TimetableSlot.period_number).where(
            TimetableSlot.school_id == school_id,
            TimetableSlot.day_of_week == day_of_week,
        )
    ).all()
    busy: dict[int, set[int]] = {}
    for teacher_id, period in rows:
        busy.setdefault(int(teacher_id), set()).add(int(period))
    return busy


def _absent_teacher_ids(db: Session, school_id: int, day: dt.date) -> set[int]:
    rows = db.execute(
        select(TeacherAbsence.teacher_id).where(
            TeacherAbsence.school_id == school_id,
            TeacherAbsence.absence_date == day,
            TeacherAbsence.status != "cancelled",
        )
    ).all()
    return {int(row[0]) for row in rows}


def _qualifies(keywords: tuple[str, ...], haystack: str | None) -> bool:
    if not haystack:
        return False
    lowered = haystack.casefold()
    return any(keyword in lowered for keyword in keywords)


def _subject_codes_by_id(db: Session, school_id: int) -> dict[int, str]:
    """subject_id -> subject_code for the tenant."""
    rows = db.execute(
        select(Subject.id, Subject.subject_code).where(Subject.school_id == school_id)
    ).all()
    return {int(sid): str(code) for sid, code in rows}


def rank_candidates(
    db: Session,
    *,
    school_id: int,
    subject: Subject,
    day_of_week: int,
    period_number: int,
    excluded_teacher_ids: set[int],
    teacher_subjects: dict[int, set[int]],
    busy_by_teacher: dict[int, set[int]],
    teachers_by_id: dict[int, User],
) -> list[Candidate]:
    """Rank every eligible substitute for one absent (day, period) slot."""
    candidates: list[Candidate] = []
    group = SUBJECT_GROUPS.get(subject.subject_code)
    keywords = SUBJECT_KEYWORDS.get(subject.subject_code, ())
    codes_by_id = _subject_codes_by_id(db, school_id)

    for teacher_id, teacher in teachers_by_id.items():
        if teacher_id in excluded_teacher_ids:
            continue
        busy = sorted(busy_by_teacher.get(teacher_id, set()))
        if period_number in busy:
            continue  # occupied period slot — never a candidate

        candidate = Candidate(
            teacher_id=teacher_id,
            full_name=_display_name(teacher),
            staff_identifier=teacher.staff_identifier,
            designation=teacher.designation,
            qualifications=teacher.qualifications,
            busy_periods=busy,
        )

        if subject.id in teacher_subjects.get(teacher_id, set()):
            candidate.score += SCORE_EXACT_SUBJECT
            candidate.reasons.append(f"Currently teaches {subject.subject_name}")

        if _qualifies(keywords, " ".join(filter(None, [teacher.qualifications, teacher.designation]))):
            candidate.score += SCORE_QUALIFICATION
            candidate.reasons.append("Department qualification match")

        their_groups = {
            SUBJECT_GROUPS.get(codes_by_id.get(sid, ""))
            for sid in teacher_subjects.get(teacher_id, set())
        }
        if group and group in their_groups:
            candidate.score += SCORE_DEPARTMENT
            candidate.reasons.append(f"Same department ({group})")

        # Light-load tiebreaker: prefer colleagues with fewer booked periods.
        candidate.score += max(0, 4 - len(busy))
        if not candidate.reasons:
            candidate.reasons.append(
                f"Available at period {period_number} ({len(busy)} booked today)"
            )
        candidates.append(candidate)

    candidates.sort(key=lambda c: (-c.score, c.full_name.casefold(), c.teacher_id))
    return candidates


def recommendation_payload(db: Session, absence: TeacherAbsence) -> dict:
    """Build the coverage recommendation panel for a logged absence.

    Returns every timetable slot the absent teacher owns on the absence date
    (opening slots first), each with the ranked substitute shortlist.
    """
    school_id = absence.school_id
    day = absence.absence_date
    day_of_week = day.weekday()

    slots = (
        db.execute(
            select(TimetableSlot)
            .where(
                TimetableSlot.school_id == school_id,
                TimetableSlot.teacher_id == absence.teacher_id,
                TimetableSlot.day_of_week == day_of_week,
            )
            .order_by(TimetableSlot.period_number)
        )
        .scalars()
        .all()
    )

    confirmed = {
        (int(row[0]), int(row[1]))
        for row in db.execute(
            select(SubstitutionAssignment.class_id, SubstitutionAssignment.period_number).where(
                SubstitutionAssignment.absence_id == absence.id,
                SubstitutionAssignment.status.in_(("confirmed", "completed")),
            )
        ).all()
    }

    # Work with narrow identity data only — no full-ORM fan-out.
    staff_rows = db.execute(
        select(User).where(
            User.school_id == school_id,
            User.role == "teacher",
            User.is_active.is_(True),
        )
    ).scalars().all()
    teachers_by_id = {int(t.id): t for t in staff_rows}

    teacher_subjects = _teacher_subject_map(db, school_id)
    busy_by_teacher = _teacher_day_busy(db, school_id, day_of_week)
    absent_ids = _absent_teacher_ids(db, school_id, day)
    excluded = absent_ids | {int(absence.teacher_id)}

    subjects = {
        int(s.id): s
        for s in db.execute(select(Subject).where(Subject.school_id == school_id)).scalars().all()
    }
    classes = {
        int(c.id): c
        for c in db.execute(select(SchoolClass).where(SchoolClass.school_id == school_id)).scalars().all()
    }

    slot_payloads: list[dict] = []
    for slot in slots:
        subject = subjects.get(int(slot.subject_id))
        klass = classes.get(int(slot.class_id))
        candidates = (
            rank_candidates(
                db,
                school_id=school_id,
                subject=subject,
                day_of_week=day_of_week,
                period_number=int(slot.period_number),
                excluded_teacher_ids=excluded,
                teacher_subjects=teacher_subjects,
                busy_by_teacher=busy_by_teacher,
                teachers_by_id=teachers_by_id,
            )
            if subject
            else []
        )
        slot_payloads.append(
            {
                "slot_id": int(slot.id),
                "period_number": int(slot.period_number),
                "class_id": int(slot.class_id),
                "class_label": f"{klass.class_level} {klass.class_stream}" if klass else None,
                "subject_id": int(slot.subject_id),
                "subject_name": subject.subject_name if subject else None,
                "covered": (int(slot.class_id), int(slot.period_number)) in confirmed,
                "candidates": [c.as_dict() for c in candidates[:5]],
            }
        )

    uncovered = sum(1 for s in slot_payloads if not s["covered"])
    return {
        "absence_id": int(absence.id),
        "teacher_id": int(absence.teacher_id),
        "teacher_name": _display_name(absence.teacher) if absence.teacher else None,
        "absence_date": day.isoformat(),
        "day_label": WEEKDAY_LABELS[day_of_week] if 0 <= day_of_week < len(WEEKDAY_LABELS) else None,
        "reason": absence.reason,
        "status": absence.status,
        "slots": slot_payloads,
        "slots_total": len(slot_payloads),
        "slots_uncovered": uncovered,
    }


def auto_assign_best(
    db: Session, absence: TeacherAbsence, assigned_by: int | None
) -> list[SubstitutionAssignment]:
    """Confirm the top-ranked candidate for every still-open slot."""
    panel = recommendation_payload(db, absence)
    created: list[SubstitutionAssignment] = []
    for slot in panel["slots"]:
        if slot["covered"] or not slot["candidates"]:
            continue
        best = slot["candidates"][0]
        assignment = SubstitutionAssignment(
            school_id=absence.school_id,
            absence_id=absence.id,
            class_id=slot["class_id"],
            subject_id=slot["subject_id"],
            original_teacher_id=absence.teacher_id,
            substitute_teacher_id=best["teacher_id"],
            day_of_week=absence.absence_date.weekday(),
            date_for_day=absence.absence_date,
            period_number=slot["period_number"],
            status="confirmed",
            match_score=best["score"],
            match_reason="; ".join(best["reasons"]) or "Engine recommendation",
            assigned_by=assigned_by,
        )
        db.add(assignment)
        created.append(assignment)
    if created:
        _refresh_absence_status(db, absence)
    return created


def _refresh_absence_status(db: Session, absence: TeacherAbsence) -> None:
    """Mark the absence covered once every slot has a confirmed substitute."""
    slots_count = db.execute(
        select(TimetableSlot.id).where(
            TimetableSlot.school_id == absence.school_id,
            TimetableSlot.teacher_id == absence.teacher_id,
            TimetableSlot.day_of_week == absence.absence_date.weekday(),
        )
    ).all()
    confirmed_count = db.execute(
        select(SubstitutionAssignment.id).where(
            SubstitutionAssignment.absence_id == absence.id,
            SubstitutionAssignment.status.in_(("confirmed", "completed")),
        )
    ).all()
    if slots_count and len(confirmed_count) >= len(slots_count):
        absence.status = "covered"
        absence.resolved_at = dt.datetime.now()
    elif absence.status == "covered":
        absence.status = "logged"
        absence.resolved_at = None

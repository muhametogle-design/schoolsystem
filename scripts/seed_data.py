"""Initial data pipeline for the multi-tenant school-management system.

The supported demo estate contains *only* the five requested schools. Every
school receives Class 1–12, the same ten mandatory subjects, at least eight
teachers, explicit class/subject/teacher mappings, a sequential two-letter
roll-number allocator, attendance history, published/draft marks, and a
private billing scaffold.

Run:
    python -m scripts.seed_data --reset

``--reset`` removes prior local/demo records before seeding. It is intentionally
explicit for real deployments; auto-seeding upgrades only the legacy placeholder
estate, never a school database that contains unknown customer records.
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AcademicYear,
    Base,
    CommunicationLog,
    DailySubmissionLog,
    ExamSubmissionEvent,
    FEE_STATUSES,
    LiveAttendance,
    PaymentTransaction,
    PrivateSchool,
    SchoolClass,
    Student,
    StudentGrade,
    StudentInvoice,
    Subject,
    TuitionRate,
    User,
)
from app.services.school_template import (
    CORE_SUBJECTS,
    assign_complete_curriculum,
    provision_school_template,
)
from app.services.student_id import generate_school_roll_number, generate_unique_staff_identifier

rng = random.Random(20260830)

FIRST_NAMES = [
    "Amina", "Mohamed", "Fatima", "Ahmed", "Zainab", "Yusuf", "Hodan", "Ali",
    "Sagal", "Abdisalam", "Ifrah", "Liban", "Muna", "Guled", "Deqa", "Khadar",
    "Ayaan", "Bashir", "Fadumo", "Warsame", "Naima", "Omar", "Hani", "Jama",
]
LAST_NAMES = [
    "Farah", "Ali", "Hassan", "Abdi", "Yusuf", "Adan", "Ibrahim", "Osman",
    "Mohamed", "Nur", "Warsame", "Diriye", "Gedi", "Hersi", "Jama", "Kahin",
]
GUARDIAN_REL = ["Mother", "Father", "Uncle", "Aunt", "Grandmother", "Grandfather"]
DISTRICTS = [
    "Subulaha", "Waabari", "Suldaan Yuusuf", "Daami",
    "Xero Awr", "Maxamuud Haybe", "Gacan Libaax", "Jireeye",
]
FEE_STATUS_WEIGHTS = {"PAID": 46, "PENDING": 22, "NOT_PAID": 24, "SCHOLARSHIP": 8}
CLASS_TRACKS = [f"Class {n}" for n in range(1, 13)]
PUBLISHED_EXAM = "End of Term 1"
DRAFT_EXAM = "Mid-Term 1"

# Every required school is deliberately explicit: codes are not inferred.
SCHOOLS = [
    {
        "school_code": "IL",
        "state_license_number": "SOL/PS/2026/IL01",
        "school_name": "Ilays Educational Academy",
        "proprietor_name": "Halima Farah",
        "contact_phone": "+252-63-400-1101",
        "contact_email": "office@ilays.edu.so",
        "physical_address": "Masalaha Quarter, Laascaanood",
        "domain": "ilays.edu.so",
        "streams": ["A", "B"],
        "submitted_today": ("09:42", True),
    },
    {
        "school_code": "MY",
        "state_license_number": "SOL/PS/2026/MY02",
        "school_name": "Muse Yusuf Secondary School",
        "proprietor_name": "Abdisalam Nur",
        "contact_phone": "+252-63-400-1102",
        "contact_email": "office@museyusuf.edu.so",
        "physical_address": "Boameh Street, Laascaanood",
        "domain": "museyusuf.edu.so",
        "streams": ["A"],
        # Deliberate live compliance example for the State dashboard.
        "submitted_today": None,
    },
    {
        "school_code": "NG",
        "state_license_number": "SOL/PS/2026/NG03",
        "school_name": "Nugaal High School",
        "proprietor_name": "Deqa Hersi",
        "contact_phone": "+252-63-400-1103",
        "contact_email": "office@nugaal.edu.so",
        "physical_address": "Airport Road, Laascaanood",
        "domain": "nugaal.edu.so",
        "streams": ["A", "B"],
        "submitted_today": ("10:17", True),
    },
    {
        "school_code": "AQ",
        "state_license_number": "SOL/PS/2026/AQ04",
        "school_name": "ALQALAM SCHOOLS",
        "proprietor_name": "Muna Jama",
        "contact_phone": "+252-63-400-1104",
        "contact_email": "office@alqalam.edu.so",
        "physical_address": "Xero Awr, Laascaanood",
        "domain": "alqalam.edu.so",
        "streams": ["A"],
        "submitted_today": ("10:48", True),
    },
    {
        "school_code": "LB",
        "state_license_number": "SOL/PS/2026/LB05",
        "school_name": "Las Anod Boarding Secondary School (LBSS)",
        "proprietor_name": "Warsame Adan",
        "contact_phone": "+252-63-400-1105",
        "contact_email": "office@lbss.edu.so",
        "physical_address": "Jireeye Road, Laascaanood",
        "domain": "lbss.edu.so",
        "streams": ["A", "B"],
        "submitted_today": ("11:17", True),
    },
]

# Previously shipped placeholders that can be safely auto-upgraded only when
# they are the *entire* local estate.
LEGACY_PLACEHOLDER_SCHOOLS = {
    "Greenfield Academy",
    "Horizon Preparatory School",
    "Crescent International School",
}

TEACHER_PROFILES = [
    ("Ayaan", "Hassan", "Somali and History Teacher", "B.Ed Languages — University of Hargeisa"),
    ("Khadar", "Ali", "Arabic and Islamic Studies Teacher", "B.Ed Arabic & Islamic Studies"),
    ("Hodan", "Adan", "English Teacher", "B.Ed English Language"),
    ("Mohamed", "Farah", "Mathematics Teacher", "B.Sc Mathematics, PGDE"),
    ("Ifrah", "Yusuf", "Physics Teacher", "B.Sc Physics, PGDE"),
    ("Bashir", "Nur", "Chemistry Teacher", "B.Sc Chemistry, PGDE"),
    ("Sagal", "Ibrahim", "Biology Teacher", "B.Sc Biology, PGDE"),
    ("Fadumo", "Osman", "Humanities Teacher", "B.Ed Social Sciences"),
]


def last_school_days(count: int) -> list[dt.date]:
    """Most recent weekdays before today, newest first."""
    days: list[dt.date] = []
    cursor = dt.date.today()
    while len(days) < count:
        cursor -= dt.timedelta(days=1)
        if cursor.weekday() < 5:
            days.append(cursor)
    return days


def _teacher_for_subject(teachers: list[User], subject: Subject) -> User:
    subject_index = {name: index for index, (_, name) in enumerate(CORE_SUBJECTS)}
    return teachers[subject_index.get(subject.subject_name, 0) % len(teachers)]


def _create_staff(session: Session, school: PrivateSchool, year: str) -> tuple[User, list[User]]:
    domain = next(cfg["domain"] for cfg in SCHOOLS if cfg["school_code"] == school.school_code)
    manager = User(
        school_id=school.id,
        email=f"manager@{domain}",
        password_hash=hash_password("School@2026"),
        role="school_manager",
        first_name="Ibrahim",
        last_name=school.school_name.split()[0].title(),
        staff_identifier=generate_unique_staff_identifier(session, "school_manager", year),
        phone=f"+252-63-{rng.randint(4200000, 4299999)}",
        qualifications="M.Ed Educational Leadership — University of Hargeisa",
        designation="Principal / School Administrator",
        bio="Tenant administrator and principal officer of record.",
        is_active=True,
    )
    teachers: list[User] = []
    for number, (first, last, designation, qualifications) in enumerate(TEACHER_PROFILES, start=1):
        # The first teacher retains the convenient `teacher@…` account; the
        # rest are distinct staff profiles with equivalent demo credentials.
        local = "teacher" if number == 1 else f"teacher{number}"
        teachers.append(
            User(
                school_id=school.id,
                email=f"{local}@{domain}",
                password_hash=hash_password("Teach@2026"),
                role="teacher",
                first_name=first,
                last_name=last,
                staff_identifier=generate_unique_staff_identifier(session, "teacher", year),
                phone=f"+252-63-{rng.randint(4300000, 4399999)}",
                qualifications=qualifications,
                designation=designation,
                bio=f"{designation} at {school.school_name}.",
                is_active=True,
            )
        )
    session.add_all([manager, *teachers])
    session.flush()
    return manager, teachers


def _add_students(
    session: Session,
    school: PrivateSchool,
    classes: Iterable[SchoolClass],
    today: dt.date,
) -> dict[int, list[Student]]:
    students_by_class: dict[int, list[Student]] = {}
    for klass in classes:
        level_num = int(klass.class_level.split()[-1])
        roster_size = 6 + (level_num % 4)
        for index in range(roster_size):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            roll_number = generate_school_roll_number(session, school)
            student = Student(
                school_id=school.id,
                national_student_id=roll_number,
                roll_number=roll_number,
                current_class_id=klass.id,
                first_name=first,
                last_name=last,
                date_of_birth=dt.date(today.year - 6 - level_num, rng.randint(1, 12), rng.randint(1, 28)),
                gender=rng.choice(["Male", "Female"]),
                guardian_name=f"{rng.choice(FIRST_NAMES)} {last}",
                guardian_relationship=rng.choice(GUARDIAN_REL),
                guardian_phone=f"+252-63-{rng.randint(4000000, 4199999)}",
                guardian_email=f"guardian.{school.school_code.lower()}.{last.lower()}{index}@mail.so",
                emergency_contact_phone=f"+252-63-{rng.randint(5000000, 5199999)}",
                physical_address=(
                    f"House No. {rng.randint(1, 240)}, {rng.choice(DISTRICTS)} District, Laascaanood"
                ),
                fee_status=rng.choices(
                    list(FEE_STATUS_WEIGHTS), weights=list(FEE_STATUS_WEIGHTS.values())
                )[0],
                enrollment_date=today - dt.timedelta(days=rng.randint(30, 400)),
                is_active=True,
            )
            session.add(student)
            students_by_class.setdefault(klass.id, []).append(student)
    session.flush()
    return students_by_class


def _add_marks(
    session: Session,
    school: PrivateSchool,
    academic_year: AcademicYear,
    classes: list[SchoolClass],
    students_by_class: dict[int, list[Student]],
    teachers: list[User],
) -> None:
    subjects = (
        session.execute(select(Subject).where(Subject.school_id == school.id)).scalars().all()
    )
    by_key = {(subject.class_level, subject.subject_code.split("-")[0]): subject for subject in subjects}
    plan = {
        "MAT": CLASS_TRACKS,
        "ENG": CLASS_TRACKS,
        "PHY": [f"Class {number}" for number in range(6, 13)],
    }
    for klass in classes:
        roster = students_by_class[klass.id]
        for code, levels in plan.items():
            if klass.class_level not in levels:
                continue
            subject = by_key[(klass.class_level, code)]
            teacher = _teacher_for_subject(teachers, subject)
            released = 0
            for student in roster:
                session.add(
                    StudentGrade(
                        school_id=school.id,
                        student_id=student.id,
                        class_id=klass.id,
                        subject_id=subject.id,
                        academic_year_id=academic_year.id,
                        exam_name=PUBLISHED_EXAM,
                        numeric_score=round(rng.uniform(42, 98), 2),
                        is_published=True,
                        recorded_by=teacher.id,
                    )
                )
                released += 1
            session.add(
                ExamSubmissionEvent(
                    school_id=school.id,
                    class_id=klass.id,
                    subject_id=subject.id,
                    academic_year_id=academic_year.id,
                    exam_name=PUBLISHED_EXAM,
                    records_released=released,
                    published_by=teacher.id,
                    published_at=dt.datetime.now() - dt.timedelta(days=rng.randint(1, 9)),
                )
            )

    # Draft marks are intentionally withheld from State query C.
    draft_class = next(klass for klass in classes if klass.class_level == "Class 4")
    for student in students_by_class[draft_class.id]:
        for code in ("BIO", "HIS"):
            subject = by_key[("Class 4", code)]
            session.add(
                StudentGrade(
                    school_id=school.id,
                    student_id=student.id,
                    class_id=draft_class.id,
                    subject_id=subject.id,
                    academic_year_id=academic_year.id,
                    exam_name=DRAFT_EXAM,
                    numeric_score=round(rng.uniform(38, 96), 2),
                    is_published=False,
                    recorded_by=_teacher_for_subject(teachers, subject).id,
                )
            )


def _add_attendance(
    session: Session,
    school: PrivateSchool,
    classes: list[SchoolClass],
    students_by_class: dict[int, list[Student]],
    teacher: User,
    submitted_today: tuple[str, bool] | None,
    today: dt.date,
) -> None:
    history_days = last_school_days(10)
    # A small historic breach makes the alert audit feed meaningful without
    # changing the requested active school set.
    breach_indexes = [2] if school.school_code == "MY" else []
    for index, day in enumerate(history_days):
        if index in breach_indexes:
            session.add(
                DailySubmissionLog(
                    school_id=school.id,
                    log_date=day,
                    attendance_submitted=False,
                    alarm_triggered=True,
                    alarm_raised_at=dt.datetime.combine(day, dt.time(15, 0)),
                )
            )
            session.add(
                CommunicationLog(
                    school_id=school.id,
                    recipient_phone="STATE_DASHBOARD_ALARM_PIPELINE",
                    message_type="Red_Alarm",
                    message_content=(
                        f"CRITICAL COMPLIANCE BREACH: {school.school_name} missed the attendance deadline."
                    ),
                    delivery_status="Delivered",
                    timestamp_sent=dt.datetime.combine(day, dt.time(15, 0)),
                )
            )
            continue
        for klass in classes:
            for student in students_by_class[klass.id]:
                session.add(
                    LiveAttendance(
                        school_id=school.id,
                        class_id=klass.id,
                        student_id=student.id,
                        date=day,
                        status=rng.choices(["Present", "Absent", "Late"], weights=[90, 6, 4])[0],
                        recorded_by=teacher.id,
                    )
                )
        session.add(
            DailySubmissionLog(
                school_id=school.id,
                log_date=day,
                attendance_submitted=True,
                attendance_submitted_at=dt.datetime.combine(day, dt.time(rng.randint(9, 11), rng.randint(0, 59))),
                alarm_triggered=False,
            )
        )

    if submitted_today:
        for klass in classes:
            for student in students_by_class[klass.id]:
                session.add(
                    LiveAttendance(
                        school_id=school.id,
                        class_id=klass.id,
                        student_id=student.id,
                        date=today,
                        status=rng.choices(["Present", "Absent", "Late"], weights=[88, 8, 4])[0],
                        recorded_by=teacher.id,
                    )
                )
        hour, minute = (int(value) for value in submitted_today[0].split(":"))
        session.add(
            DailySubmissionLog(
                school_id=school.id,
                log_date=today,
                attendance_submitted=True,
                attendance_submitted_at=dt.datetime.combine(today, dt.time(hour, minute)),
                alarm_triggered=False,
            )
        )
    else:
        # A partial live roster keeps the missing submission visible to the
        # State until the 15:00 worker raises a red alarm.
        for student in students_by_class[classes[0].id][:5]:
            session.add(
                LiveAttendance(
                    school_id=school.id,
                    class_id=classes[0].id,
                    student_id=student.id,
                    date=today,
                    status="Present",
                    recorded_by=teacher.id,
                )
            )


def _add_private_finance(
    session: Session,
    school: PrivateSchool,
    academic_year: AcademicYear,
    students_by_class: dict[int, list[Student]],
    manager: User,
    today: dt.date,
) -> None:
    students = [student for roster in students_by_class.values() for student in roster]
    for student in rng.sample(students, k=min(12, len(students))):
        amount = round(rng.uniform(120, 420), 2)
        scenario = rng.choice(["settled", "partial", "outstanding", "scholarship"])
        if scenario == "settled":
            paid, status = amount, "PAID"
        elif scenario == "partial":
            paid, status = round(amount * rng.choice([0.25, 0.5, 0.75]), 2), "PENDING"
        elif scenario == "scholarship":
            paid, status = amount, "SCHOLARSHIP"
        else:
            paid, status = 0.0, "NOT_PAID"
        invoice = StudentInvoice(
            school_id=school.id,
            student_id=student.id,
            academic_year_id=academic_year.id,
            description=f"Term 1 tuition — {student.first_name} {student.last_name}",
            amount_due=amount,
            amount_paid=paid,
            due_date=today + dt.timedelta(days=rng.randint(-15, 45)),
            status=status,
        )
        session.add(invoice)
        session.flush()
        if paid > 0 and status != "SCHOLARSHIP":
            session.add(
                PaymentTransaction(
                    school_id=school.id,
                    invoice_id=invoice.id,
                    amount=paid,
                    payment_method=rng.choice(["Cash", "Mobile_Money", "Bank_Transfer", "Card"]),
                    reference_number=f"PAY-{invoice.id:05d}",
                    paid_at=dt.datetime.now() - dt.timedelta(days=rng.randint(1, 20)),
                    received_by=manager.id,
                )
            )


def seed_if_empty(session: Session) -> bool:
    existing = session.execute(select(PrivateSchool.school_name)).scalars().all()
    if not existing:
        seed(session)
        return True
    # Upgrade only the known historical placeholder demo. Customer-created
    # schools are never deleted by a server restart.
    if set(existing).issubset(LEGACY_PLACEHOLDER_SCHOOLS):
        reset_seed_data(session)
        seed(session)
        return True
    return False


def reset_seed_data(session: Session) -> None:
    """Remove all local sample/customer rows in dependency-safe order.

    This is used by the explicit CLI reset command, and by the safe migration
    path when the database contains only the old built-in placeholder estate.
    """
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()


def seed(session: Session) -> None:
    """Create exactly the requested five-school estate."""
    if session.execute(select(func.count(PrivateSchool.id))).scalar_one():
        raise RuntimeError("Database is not empty; use reset_seed_data() before seed()")

    today = dt.date.today()
    current_year = f"{today.year}-{today.year + 1}"
    academic_year = AcademicYear(
        label=current_year,
        start_date=today.replace(month=9, day=1) if today.month < 9 else today,
        end_date=today.replace(year=today.year + 1, month=7, day=31),
        is_current=True,
    )
    session.add(academic_year)
    session.flush()

    # Distinct State roles: State Admin manages tenant configuration; Inspector
    # has cross-school read-only academic visibility.
    session.add_all(
        [
            User(
                school_id=None,
                email="stateadmin@education.gov",
                password_hash=hash_password("StateAdmin@2026"),
                role="state_admin",
                first_name="Amina",
                last_name="Yusuf",
                designation="State Education Administrator",
                is_active=True,
            ),
            User(
                school_id=None,
                email="inspector@education.gov",
                password_hash=hash_password("State@2026"),
                role="inspector",
                first_name="Ismail",
                last_name="Hussein",
                designation="School Inspector",
                is_active=True,
            ),
        ]
    )
    session.flush()

    enrollment_year = current_year.split("-")[0]
    for cfg in SCHOOLS:
        school = PrivateSchool(
            state_license_number=cfg["state_license_number"],
            school_code=cfg["school_code"],
            school_name=cfg["school_name"],
            proprietor_name=cfg["proprietor_name"],
            contact_phone=cfg["contact_phone"],
            contact_email=cfg["contact_email"],
            physical_address=cfg["physical_address"],
            accreditation_status="Active",
            billing_contact_name=cfg["proprietor_name"],
            billing_phone=cfg["contact_phone"],
            billing_email=f"billing@{cfg['domain']}",
            billing_address=cfg["physical_address"],
            billing_notes="Initial termly tuition schedule. Tenant-private billing data.",
        )
        session.add(school)
        session.flush()
        manager, teachers = _create_staff(session, school, enrollment_year)
        provision_school_template(session, school, streams=cfg["streams"], default_tuition_amount=100.0)
        # Fetch post-template classes in natural order and fully populate every
        # class/subject mapping using the named staff profiles.
        classes = (
            session.execute(select(SchoolClass).where(SchoolClass.school_id == school.id))
            .scalars()
            .all()
        )
        classes.sort(key=lambda klass: (int(klass.class_level.split()[-1]), klass.class_stream, klass.id))
        assign_complete_curriculum(session, school, teachers, overwrite=True)
        session.flush()

        students_by_class = _add_students(session, school, classes, today)
        _add_marks(session, school, academic_year, classes, students_by_class, teachers)
        _add_attendance(
            session,
            school,
            classes,
            students_by_class,
            teachers[0],
            cfg["submitted_today"],
            today,
        )
        _add_private_finance(session, school, academic_year, students_by_class, manager, today)

    # Operations tier: timetable, syllabus tracker, demo absences, biometric
    # history (kept in a dedicated module so this file stays readable).
    from scripts.seed_ops import seed_operations

    seed_operations(session)

    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the school-system database")
    parser.add_argument("--reset", action="store_true", help="clear existing records before seeding")
    args = parser.parse_args()
    from app.core.db import SessionLocal, init_db, set_rls_context

    init_db()
    with SessionLocal() as session:
        # Seed data is an operator bootstrap task, not a tenant request. This
        # lets a freshly provisioned PostgreSQL database seed under FORCE RLS.
        set_rls_context(session, school_id=None, role="state_admin")
        if args.reset:
            reset_seed_data(session)
            seed(session)
            print("Reset and seeded the five-school initial estate.")
        else:
            created = seed_if_empty(session)
            print("Seeded the five-school initial estate." if created else "Database already populated — skipped.")


if __name__ == "__main__":
    main()

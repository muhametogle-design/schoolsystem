"""STEP 5 — COMPREHENSIVE SEEDING PIPELINE.

Automated mock seed data so every analytics panel functions immediately:

  * registers 3 mock private schools (all Active),
  * class tracks spanning Class 1 -> Class 12 for each school,
  * mock student tracking profiles with unique auto-generated National IDs
    (STU-YYYY-XY123) and guardian phone/email records,
  * realistic sample attendance HISTORIES for the past school days with
    submitted daily logs (plus one historical RED ALARM breach day), and
  * published examination grades carrying exam_submission_events tokens.

Run standalone:  python -m scripts.seed_data
"""

from __future__ import annotations

import datetime as dt
import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AcademicYear,
    CommunicationLog,
    DailySubmissionLog,
    ExamSubmissionEvent,
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
from app.services.student_id import generate_unique_national_student_id

rng = random.Random(2026)

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
CLASS_TRACKS = [f"Class {n}" for n in range(1, 13)]  # Class 1 -> Class 12
PUBLISHED_EXAM = "End of Term 1"
DRAFT_EXAM = "Mid-Term 1"
SUBJECT_MENU = [
    ("MATH", "Mathematics"),
    ("ENG", "English Language"),
    ("SCI", "Integrated Science"),
    ("SST", "Social Studies"),
]

SCHOOLS = [
    {
        "state_license_number": "SOL/PS/2026/001",
        "school_name": "Greenfield Academy",
        "proprietor_name": "Halima Farah",
        "contact_phone": "+252-63-400-1101",
        "contact_email": "office@greenfield.edu",
        "physical_address": "Masalaha Quarter, Laascaanood",
        "streams": ["A"],
        "submitted_today": ("09:42", True),
        "publishes": ("MATH", "ENG"),   # subjects released for Class 5-8
    },
    {
        "state_license_number": "SOL/PS/2026/002",
        "school_name": "Horizon Preparatory School",
        "proprietor_name": "Abdisalam Nur",
        "contact_phone": "+252-63-400-1102",
        "contact_email": "office@horizon.edu",
        "physical_address": "Boameh Street, Laascaanood",
        "streams": ["A"],
        "submitted_today": None,        # ← today's roster missing => 15:00 RED ALARM
        "publishes": ("MATH",),
    },
    {
        "state_license_number": "SOL/PS/2026/003",
        "school_name": "Crescent International School",
        "proprietor_name": "Deqa Hersi",
        "contact_phone": "+252-63-400-1103",
        "contact_email": "office@crescent.edu",
        "physical_address": "Airport Road, Laascaanood",
        "streams": ["A"],
        "submitted_today": ("11:17", True),
        "publishes": ("MATH", "ENG"),
    },
]


def last_school_days(count: int) -> list[dt.date]:
    """The most recent `count` weekdays before today."""
    days: list[dt.date] = []
    cursor = dt.date.today()
    while len(days) < count:
        cursor -= dt.timedelta(days=1)
        if cursor.weekday() < 5:  # Mon-Fri
            days.append(cursor)
    return days  # ordered most-recent-first


def seed_if_empty(session: Session) -> bool:
    if session.execute(select(func.count(PrivateSchool.id))).scalar_one() > 0:
        return False
    seed(session)
    return True


def seed(session: Session) -> None:
    today = dt.date.today()
    current_year = f"{today.year}-{today.year + 1}"
    history_days = last_school_days(10)
    breach_day = history_days[0]  # Horizon's historical RED ALARM day

    academic_year = AcademicYear(
        label=current_year,
        start_date=today.replace(month=9, day=1) if today.month < 9 else today,
        end_date=today.replace(year=today.year + 1, month=7, day=31),
        is_current=True,
    )
    session.add(academic_year)
    session.flush()

    # ---- State Government super-admin (school_id NULL) ----
    session.add(
        User(
            school_id=None,
            email="inspector@education.gov",
            password_hash=hash_password("State@2026"),
            role="state_inspector",
            first_name="Amina",
            last_name="Yusuf",
        )
    )

    enroll_year = current_year.split("-")[0]

    for cfg in SCHOOLS:
        school = PrivateSchool(
            state_license_number=cfg["state_license_number"],
            school_name=cfg["school_name"],
            proprietor_name=cfg["proprietor_name"],
            contact_phone=cfg["contact_phone"],
            contact_email=cfg["contact_email"],
            physical_address=cfg["physical_address"],
            accreditation_status="Active",
        )
        session.add(school)
        session.flush()

        domain = cfg["contact_email"].split("@")[1]
        manager = User(
            school_id=school.id,
            email=f"manager@{domain}",
            password_hash=hash_password("School@2026"),
            role="school_manager",
            first_name="Ibrahim",
            last_name=cfg["school_name"].split()[0],
        )
        teacher = User(
            school_id=school.id,
            email=f"teacher@{domain}",
            password_hash=hash_password("Teach@2026"),
            role="teacher",
            first_name="Hodan",
            last_name="Adan",
        )
        session.add_all([manager, teacher])
        session.flush()

        # ---- Class tracks: Class 1 -> Class 12 ----
        classes: dict[str, SchoolClass] = {}
        for level in CLASS_TRACKS:
            for stream in cfg["streams"]:
                klass = SchoolClass(
                    school_id=school.id,
                    class_level=level,
                    class_stream=stream,
                    room_number=f"R-{level.split()[-1]}{stream}",
                    class_teacher_id=teacher.id,
                )
                session.add(klass)
                classes[f"{level}-{stream}"] = klass
        session.flush()

        # ---- Subjects ----
        subjects: dict[str, Subject] = {}
        for level in CLASS_TRACKS:
            for code, name in SUBJECT_MENU:
                subject = Subject(
                    school_id=school.id,
                    subject_code=f"{code}-{level.split()[-1]}",
                    subject_name=name,
                    class_level=level,
                )
                session.add(subject)
                subjects[f"{code}-{level}"] = subject
        session.flush()

        # ---- Student tracking profiles (unique auto-generated National IDs) ----
        students_by_class: dict[int, list[Student]] = {}
        for key, klass in classes.items():
            level_num = int(klass.class_level.split()[-1])
            roster_size = 6 + (level_num % 4)
            for i in range(roster_size):
                first = rng.choice(FIRST_NAMES)
                last = rng.choice(LAST_NAMES)
                student = Student(
                    school_id=school.id,
                    national_student_id=generate_unique_national_student_id(session, enroll_year),
                    current_class_id=klass.id,
                    first_name=first,
                    last_name=last,
                    date_of_birth=dt.date(today.year - 6 - level_num, rng.randint(1, 12), rng.randint(1, 28)),
                    gender=rng.choice(["Male", "Female"]),
                    guardian_name=f"{rng.choice(FIRST_NAMES)} {last}",
                    guardian_relationship=rng.choice(GUARDIAN_REL),
                    guardian_phone=f"+252-63-{rng.randint(4000000, 4199999)}",
                    guardian_email=f"guardian.{last.lower()}{i}@mail.so",
                    emergency_contact_phone=f"+252-63-{rng.randint(5000000, 5199999)}",
                    enrollment_date=today - dt.timedelta(days=rng.randint(30, 400)),
                    is_active=True,
                )
                session.add(student)
                students_by_class.setdefault(klass.id, []).append(student)
        session.flush()

        # ---- Published examination grades (Class 5-8, with token events) ----
        for level in ("Class 5", "Class 6", "Class 7", "Class 8"):
            for stream in cfg["streams"]:
                klass = classes[f"{level}-{stream}"]
                roster = students_by_class[klass.id]
                for code in cfg["publishes"]:
                    subject = subjects[f"{code}-{level}"]
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
                                recorded_by=manager.id,
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
                            published_by=manager.id,
                            published_at=dt.datetime.now() - dt.timedelta(days=rng.randint(1, 9)),
                        )
                    )

        # ---- Private draft marks (never tokenized → invisible to the State) ----
        draft_key = f"Class 4-{cfg['streams'][0]}"
        draft_class = classes[draft_key]
        for student in students_by_class[draft_class.id]:
            for code in ("SCI", "SST"):
                session.add(
                    StudentGrade(
                        school_id=school.id,
                        student_id=student.id,
                        class_id=draft_class.id,
                        subject_id=subjects[f"{code}-Class 4"].id,
                        academic_year_id=academic_year.id,
                        exam_name=DRAFT_EXAM,
                        numeric_score=round(rng.uniform(38, 96), 2),
                        is_published=False,
                        recorded_by=teacher.id,
                    )
                )

        # ---- Attendance history (past school days, all submitted on time) ----
        for day in history_days:
            if cfg["school_name"] == "Horizon Preparatory School" and day == breach_day:
                continue  # Horizon's historical breach day — no roster, alarm below
            for klass in classes.values():
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

        # ---- Today's attendance + 12:00 PM submission state ----
        if cfg["submitted_today"]:
            for klass in classes.values():
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
            hh, mm = (int(x) for x in cfg["submitted_today"][0].split(":"))
            session.add(
                DailySubmissionLog(
                    school_id=school.id,
                    log_date=today,
                    attendance_submitted=True,
                    attendance_submitted_at=dt.datetime.combine(today, dt.time(hh, mm)),
                    alarm_triggered=False,
                )
            )
        else:
            # Horizon: attendance entered this morning but the roster was never
            # submitted — the 15:00 worker will raise today's RED ALARM.
            first_class = next(iter(classes.values()))
            for student in students_by_class[first_class.id][:5]:
                session.add(
                    LiveAttendance(
                        school_id=school.id,
                        class_id=first_class.id,
                        student_id=student.id,
                        date=today,
                        status="Present",
                        recorded_by=teacher.id,
                    )
                )

        # ---- Private financial ledger (firewalled tier) ----
        for level in CLASS_TRACKS:
            session.add(
                TuitionRate(
                    school_id=school.id,
                    class_level=level,
                    base_tuition_amount=round(rng.uniform(60, 180), 2),
                    billing_cycle="Termly",
                )
            )
        all_students = [s for roster in students_by_class.values() for s in roster]
        for student in rng.sample(all_students, k=min(8, len(all_students))):
            amount = round(rng.uniform(120, 420), 2)
            paid = rng.choice([0, amount * 0.5, amount])
            status = "Settled" if paid >= amount else ("Partially_Paid" if paid > 0 else "Outstanding")
            invoice = StudentInvoice(
                school_id=school.id,
                student_id=student.id,
                academic_year_id=academic_year.id,
                description=f"Term 1 tuition — {student.first_name} {student.last_name}",
                amount_due=amount,
                amount_paid=round(paid, 2),
                due_date=today + dt.timedelta(days=rng.randint(5, 40)),
                status=status,
            )
            session.add(invoice)
            session.flush()
            if paid > 0:
                session.add(
                    PaymentTransaction(
                        school_id=school.id,
                        invoice_id=invoice.id,
                        amount=round(paid, 2),
                        payment_method=rng.choice(["Cash", "Mobile_Money", "Bank_Transfer"]),
                        reference_number=f"PAY-{invoice.id:05d}",
                        paid_at=dt.datetime.now() - dt.timedelta(days=rng.randint(1, 20)),
                        received_by=manager.id,
                    )
                )

    # ---- Horizon's historical RED ALARM breach (log + communication gateway) ----
    horizon = (
        session.execute(select(PrivateSchool).where(PrivateSchool.school_name == "Horizon Preparatory School"))
        .scalar_one()
    )
    session.add(
        DailySubmissionLog(
            school_id=horizon.id,
            log_date=breach_day,
            attendance_submitted=False,
            alarm_triggered=True,
            alarm_raised_at=dt.datetime.combine(breach_day, dt.time(15, 0)),
        )
    )
    session.add(
        CommunicationLog(
            school_id=horizon.id,
            recipient_phone="STATE_DASHBOARD_ALARM_PIPELINE",
            message_type="Red_Alarm",
            message_content=(
                "CRITICAL COMPLIANCE BREACH: Horizon Preparatory School has triggered a RED ALARM "
                "for failing to submit attendance logs by the 12:00 PM state deadline."
            ),
            delivery_status="Delivered",
            timestamp_sent=dt.datetime.combine(breach_day, dt.time(15, 0)),
        )
    )
    session.commit()


if __name__ == "__main__":
    from app.core.db import SessionLocal, init_db

    init_db()
    with SessionLocal() as session:
        created = seed_if_empty(session)
        print("Seeded demo data." if created else "Database already populated — skipped.")

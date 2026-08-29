"""Demo-tier bootstrap data.

Creates three licensed private schools, the state inspector account, tenant
managers/teachers, Class 1-12 structures, students with generated STU-IDs,
a mix of PRIVATE draft and PUBLISHED exam marks, today's attendance rosters
(one school deliberately unsubmitted so the 15:00 Red Alarm demo fires),
and a private financial ledger for each tenant.

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
    SecurityAuditLog,
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
EXAMS = ["Term 1 Opener", "Mid-Term 1", "End of Term 1"]

SCHOOLS = [
    {
        "state_license_number": "SOL/PS/2026/001",
        "school_name": "Greenfield Academy",
        "proprietor_name": "Halima Farah",
        "contact_phone": "+252-63-400-1101",
        "contact_email": "office@greenfield.edu",
        "physical_address": "Masalaha Quarter, Laascaanood",
        "levels": [f"Class {n}" for n in range(1, 13)],
        "streams": ["A"],
        "status": "Active",
        "submitted_today": ("09:42", True),
    },
    {
        "state_license_number": "SOL/PS/2026/002",
        "school_name": "Horizon Preparatory School",
        "proprietor_name": "Abdisalam Nur",
        "contact_phone": "+252-63-400-1102",
        "contact_email": "office@horizon.edu",
        "physical_address": "Boameh Street, Laascaanood",
        "levels": ["Class 3", "Class 4", "Class 5", "Class 6", "Class 7", "Class 8", "Class 9"],
        "streams": ["A", "B"],
        "status": "Active",
        "submitted_today": None,  # ← will trigger the 15:00 RED ALARM
    },
    {
        "state_license_number": "SOL/PS/2026/003",
        "school_name": "Crescent International School",
        "proprietor_name": "Deqa Hersi",
        "contact_phone": "+252-63-400-1103",
        "contact_email": "office@crescent.edu",
        "physical_address": "Airport Road, Laascaanood",
        "levels": ["Class 1", "Class 2", "Class 3", "Class 4", "Class 5"],
        "streams": ["A"],
        "status": "Active",
        "submitted_today": ("11:17", True),
    },
    {
        "state_license_number": "SOL/PS/2026/004",
        "school_name": "Iftin Community School",
        "proprietor_name": "Said Jama",
        "contact_phone": "+252-63-400-1104",
        "contact_email": "office@iftin.edu",
        "physical_address": "Wadada Hargeisa, Laascaanood",
        "levels": ["Class 6", "Class 7"],
        "streams": ["A"],
        "status": "Probation",  # filtered out of the active compliance map
        "submitted_today": None,
    },
]

SUBJECT_MENU = [
    ("MATH", "Mathematics"),
    ("ENG", "English Language"),
    ("SCI", "Integrated Science"),
    ("SST", "Social Studies"),
]


def seed_if_empty(session: Session) -> bool:
    if session.execute(select(func.count(PrivateSchool.id))).scalar_one() > 0:
        return False
    seed(session)
    return True


def seed(session: Session) -> None:
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

    # ---- State Government super-admin (school_id NULL) ----
    state_user = User(
        school_id=None,
        email="inspector@education.gov",
        password_hash=hash_password("State@2026"),
        role="state_inspector",
        first_name="Amina",
        last_name="Yusuf",
    )
    session.add(state_user)

    enroll_year = current_year.split("-")[0]
    school_rows: dict[str, PrivateSchool] = {}

    for cfg in SCHOOLS:
        school = PrivateSchool(
            state_license_number=cfg["state_license_number"],
            school_name=cfg["school_name"],
            proprietor_name=cfg["proprietor_name"],
            contact_phone=cfg["contact_phone"],
            contact_email=cfg["contact_email"],
            physical_address=cfg["physical_address"],
            accreditation_status=cfg["status"],
        )
        session.add(school)
        session.flush()
        school_rows[cfg["school_name"]] = school

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

        # ---- Classes 1-12 ----
        classes: dict[str, SchoolClass] = {}
        for level in cfg["levels"]:
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
        for level in cfg["levels"]:
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

        # ---- Students with generated immutable STU-IDs ----
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

        # ---- Exam marks: published (Class 5-8 Math+Eng) + private drafts ----
        publish_levels = {"Class 5", "Class 6", "Class 7", "Class 8"} & set(cfg["levels"])
        for level in publish_levels:
            for stream in cfg["streams"]:
                key = f"{level}-{stream}"
                klass = classes[key]
                roster = students_by_class[klass.id]
                for code in ("MATH", "ENG"):
                    subject = subjects[f"{code}-{level}"]
                    exam_name = "End of Term 1"
                    released = 0
                    for student in roster:
                        grade = StudentGrade(
                            school_id=school.id,
                            student_id=student.id,
                            class_id=klass.id,
                            subject_id=subject.id,
                            academic_year_id=academic_year.id,
                            exam_name=exam_name,
                            numeric_score=round(rng.uniform(42, 98), 2),
                            is_published=True,
                            recorded_by=manager.id,
                        )
                        session.add(grade)
                        released += 1
                    session.add(
                        ExamSubmissionEvent(
                            school_id=school.id,
                            class_id=klass.id,
                            subject_id=subject.id,
                            academic_year_id=academic_year.id,
                            exam_name=exam_name,
                            records_released=released,
                            published_by=manager.id,
                            published_at=dt.datetime.now() - dt.timedelta(days=rng.randint(1, 9)),
                        )
                    )

        # Private drafts (never published): every school, one class, Science + SST
        draft_level = cfg["levels"][min(2, len(cfg["levels"]) - 1)]
        for stream in cfg["streams"]:
            key = f"{draft_level}-{stream}"
            klass = classes[key]
            for student in students_by_class[klass.id]:
                for code in ("SCI", "SST"):
                    session.add(
                        StudentGrade(
                            school_id=school.id,
                            student_id=student.id,
                            class_id=klass.id,
                            subject_id=subjects[f"{code}-{draft_level}"].id,
                            academic_year_id=academic_year.id,
                            exam_name="Mid-Term 1",
                            numeric_score=round(rng.uniform(38, 96), 2),
                            is_published=False,
                            recorded_by=teacher.id,
                        )
                    )

        # ---- Today's attendance + the 12:00 PM submission state ----
        if cfg["status"] == "Active" and cfg["submitted_today"]:
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
        elif cfg["status"] == "Active":
            # Horizon: attendance entered this morning but roster NOT submitted
            # → the 15:00 worker will raise the RED ALARM on this school.
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
        for level in cfg["levels"]:
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
            status = (
                "Settled" if paid >= amount else ("Partially_Paid" if paid > 0 else "Outstanding")
            )
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

    # A historical red alarm from yesterday for the feed
    horizon = school_rows["Horizon Preparatory School"]
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
            timestamp_sent=dt.datetime.now() - dt.timedelta(days=1),
        )
    )
    session.add(
        SecurityAuditLog(
            user_id=None, role="anonymous", endpoint="/api/school/billing/summary",
            verdict="BLOCKED", detail="Seed placeholder — firewall active.",
        )
    )
    session.commit()


if __name__ == "__main__":
    from app.core.db import SessionLocal, init_db

    init_db()
    with SessionLocal() as session:
        created = seed_if_empty(session)
        print("Seeded demo data." if created else "Database already populated — skipped.")

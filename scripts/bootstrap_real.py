"""Bootstrap a REAL deployment — your own school, zero demo data.

The demo seeder (``scripts.seed_data``) installs a five-school sample estate.
This script is the opposite path for self-hosters (Termux, a laptop, a VPS):
it creates exactly two things and nothing else:

1. a State Admin account (the platform operator login you choose), and
2. your own school tenant — Class 1-12 with the mandatory subject catalogue,
   termly tuition rates, roll-number allocator, a complete subject/teacher
   mapping scaffold and 8 *template* faculty profiles you rename to your
   actual staff (their passwords are random by design; the manager resets
   them from the Teachers page).

No demo students, no demo marks, no demo attendance.

Run (after ``init_db`` — the app does it automatically on first boot):

    python -m scripts.bootstrap_real \
        --admin-email admin@yourschool.so --admin-password 'change-me' \
        --school-name "YOUR SCHOOL NAME" --license "LIC-001" \
        --manager-email manager@yourschool.so --manager-password 'change-me-too' \
        --manager-first "Your" --manager-last "Name"

Everything is idempotent-by-refusal: re-running with an email or licence that
already exists exits cleanly instead of duplicating records.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

from sqlalchemy import select

from app.core.db import SessionLocal, init_db, set_rls_context
from app.core.security import hash_password
from app.models import AcademicYear, PrivateSchool, User
from app.services.school_template import (
    allocate_school_code,
    assign_complete_curriculum,
    create_template_teachers,
    provision_school_template,
)
from app.services.student_id import generate_unique_staff_identifier


def _current_academic_year(today: dt.date) -> tuple[str, dt.date, dt.date]:
    """Somali/East-African school year: September -> July."""
    start_year = today.year if today.month >= 9 else today.year - 1
    return (
        f"{start_year}-{start_year + 1}",
        dt.date(start_year, 9, 1),
        dt.date(start_year + 1, 7, 31),
    )


def _ensure_state_admin(session, email: str, password: str, first: str, last: str) -> User:
    existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        print(f"  • State admin {email} already exists — leaving it untouched.")
        return existing
    admin = User(
        school_id=None,
        email=email,
        password_hash=hash_password(password),
        role="state_admin",
        first_name=first,
        last_name=last,
        designation="State Education Administrator",
        is_active=True,
    )
    session.add(admin)
    session.flush()
    print(f"  ✓ State admin created: {email}")
    return admin


def _provision_real_school(session, args) -> PrivateSchool | None:
    manager_email = args.manager_email.lower()
    if session.execute(select(User.id).where(User.email == manager_email)).first():
        print(f"  ! A user with {manager_email} already exists — school step skipped.")
        return session.execute(
            select(PrivateSchool).where(PrivateSchool.state_license_number == args.license)
        ).scalar_one_or_none()
    if session.execute(
        select(PrivateSchool.id).where(PrivateSchool.state_license_number == args.license)
    ).first():
        print(f"  ! Licence {args.license} is already registered — school step skipped.")
        return session.execute(
            select(PrivateSchool).where(PrivateSchool.state_license_number == args.license)
        ).scalar_one_or_none()

    code = allocate_school_code(session, args.school_name, args.school_code)
    school = PrivateSchool(
        state_license_number=args.license,
        school_code=code,
        school_name=args.school_name.strip(),
        proprietor_name=args.proprietor or None,
        contact_phone=args.phone or None,
        contact_email=args.contact_email or manager_email,
        physical_address=args.address or None,
        accreditation_status="Active",
    )
    session.add(school)
    session.flush()

    manager = User(
        school_id=school.id,
        email=manager_email,
        password_hash=hash_password(args.manager_password),
        role="school_manager",
        first_name=args.manager_first.strip(),
        last_name=args.manager_last.strip(),
        staff_identifier=generate_unique_staff_identifier(session, "school_manager", str(dt.date.today().year)),
        designation="School Administrator",
        is_active=True,
    )
    session.add(manager)
    session.flush()

    streams = [s.strip() for s in (args.streams or "A").split(",") if s.strip()]
    template = provision_school_template(session, school, streams=streams or ("A",))
    teachers = create_template_teachers(session, school, count=8)
    assignments = assign_complete_curriculum(session, school, teachers, overwrite=True)

    print(f"  ✓ School provisioned: {school.school_name} ({code})")
    print(
        "    template: {classes} classes 1-12, {subjects} subjects, "
        "{teachers} template faculty profiles, {assignments} subject mappings".format(
            classes=template["classes_created"],
            subjects=template["subjects_created"],
            teachers=len(teachers),
            assignments=assignments,
        )
    )
    print(f"  ✓ School manager login: {manager_email}")
    return school


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--admin-email", default="stateadmin@education.gov")
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--admin-first", default="State")
    parser.add_argument("--admin-last", default="Administrator")
    parser.add_argument("--school-name", required=True)
    parser.add_argument("--school-code", default=None, help="Optional 2-letter code; auto-allocated otherwise")
    parser.add_argument("--license", required=True, help="State licence number, e.g. MOE-2026-001")
    parser.add_argument("--manager-email", required=True)
    parser.add_argument("--manager-password", required=True)
    parser.add_argument("--manager-first", required=True)
    parser.add_argument("--manager-last", required=True)
    parser.add_argument("--streams", default="A", help="Comma-separated streams per class, e.g. 'A,B'")
    parser.add_argument("--proprietor", default=None)
    parser.add_argument("--phone", default=None)
    parser.add_argument("--contact-email", default=None)
    parser.add_argument("--address", default=None)
    args = parser.parse_args()

    if len(args.admin_password) < 8 or len(args.manager_password) < 8:
        print("Passwords must be at least 8 characters.", file=sys.stderr)
        return 2

    init_db()  # no-op when the API already bootstrapped the schema
    with SessionLocal() as session:
        # Bootstrap is a trusted operator action (same context as the seeder).
        set_rls_context(session, school_id=None, role="state_admin")

        today = dt.date.today()
        label, start, end = _current_academic_year(today)
        year = session.execute(select(AcademicYear).where(AcademicYear.is_current.is_(True))).scalar_one_or_none()
        if not year:
            session.add(AcademicYear(label=label, start_date=start, end_date=end, is_current=True))
            session.flush()
            print(f"  ✓ Academic year created: {label} ({start} → {end})")

        print("Platform accounts")
        _ensure_state_admin(session, args.admin_email.lower(), args.admin_password,
                            args.admin_first.strip(), args.admin_last.strip())

        print("School tenant")
        school = _provision_real_school(session, args)
        session.commit()

    print()
    print("Done. Start the platform and sign in:")
    print("  .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
    print("  → http://127.0.0.1:8000  (school manager portal, your school only)")
    print("  → the state admin login sees the oversight portal with your school listed.")
    if school is None:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

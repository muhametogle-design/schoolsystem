#!/usr/bin/env python
"""Bootstrap data for local NE-EMIS development (dev only).

Creates:
  * a state campus and a demo secondary campus
  * demo users (clerk/dean/state_admin/aggregator)
  * a dean manager (NE-MID) with a generated Ed25519 verification key
  * civil service grade tiers 1..17
  * the 2025/2026 academic year and terms

Run with:
  export DATABASE_URL=postgresql+psycopg2://neemis:neemis@localhost:5432/neemis
  python scripts/seed_data.py
"""

from __future__ import annotations

import pathlib
import sys
import uuid
from datetime import date

# Make `app` importable when the script is run directly from scripts/.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import serialization
from sqlalchemy import select

from app.core.crypto_lock import generate_keypair, public_key_pem
from app.core.db import get_engine, get_sessionmaker, set_session_tenancy
from app.core.security import hash_password
from app.models.academics import Term
from app.models.identity import AppUser, Campus, Manager
from app.models.registry import AcademicYear
from app.models.teachers import CivilServiceGrade

DEMO_PASSWORD = "ChangeMe#2026"


def main() -> None:
    factory = get_sessionmaker()
    with factory() as session:
        # The seed runs as the system role so RLS permits creating the root
        # campus + users; daily runtime roles are applied per request.
        set_session_tenancy(
            session,
            uuid.UUID("00000000-0000-0000-0000-000000000000"),
            role="system",
        )

        # Civil service grades -----------------------------------------------
        for tier in range(1, 18):
            existing = session.scalar(
                select(CivilServiceGrade).where(CivilServiceGrade.grade_tier == tier)
            )
            if existing is None:
                session.add(
                    CivilServiceGrade(
                        grade_tier=tier,
                        base_salary_naira=185_000 + (tier * 96_500),
                        hardship_multiplier=1.0 + (0.05 if tier in (6, 7, 8) else 0),
                        min_years_service=max(0, tier - 5),
                    )
                )
        session.flush()

        # Campuses ------------------------------------------------------------
        state_campus = _get_or_create_campus(
            session, "ST", "State Uplift Secondary School", "01", "state_admin"
        )
        demo_campus = _get_or_create_campus(
            session, "DEMO", "Demo Comprehensive College", "02", "campus"
        )
        session.commit()

        # Managers / users ----------------------------------------------------
        _upsert_campus_user(session, "demo.clerk", "clerk", demo_campus.id)
        _upsert_campus_user(session, "demo.dean", "dean", demo_campus.id)
        _upsert_campus_user(session, "state.admin", "state_admin", None)
        _upsert_campus_user(session, "aggregator", "aggregator", None)

        dean_user = session.scalar(
            select(AppUser).where(AppUser.username == "demo.dean")
        )
        manager = session.scalar(
            select(Manager).where(Manager.user_id == dean_user.id)
        )
        if manager is None:
            private_key, public_key = generate_keypair()
            manager = Manager(
                user_id=dean_user.id,
                campus_id=demo_campus.id,
                full_name="Demo Dean",
                designation="Dean of Studies",
                is_account_holder=True,
                verification_public_key=public_key_pem(public_key),
                signature_scheme="ed25519",
                key_version=1,
                key_activated_at=date.today(),
                is_active=True,
            )
            # Persist the private key for the local demo signing tool ONLY.
            key_dir = pathlib.Path("certs")
            key_dir.mkdir(exist_ok=True)
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            (key_dir / "demo_dean_private.pem").write_bytes(pem)
            session.add(manager)
            session.flush()
        if not manager.ne_mid:
            manager.ne_mid = "NE-MID-" + str(manager.id).replace("-", "")
        session.commit()

        # Academic year / terms ------------------------------------------------
        year = session.scalar(
            select(AcademicYear).where(AcademicYear.label == "2025/2026")
        )
        if year is None:
            year = AcademicYear(
                label="2025/2026", starts_on=date(2025, 9, 1), ends_on=date(2026, 8, 31)
            )
            session.add(year)
            session.flush()
        term_labels = ("first", "second", "third")
        for i, label in enumerate(term_labels):
            existing = session.scalar(
                select(Term).where(
                    Term.academic_year_id == year.id, Term.term_type == label
                )
            )
            if existing is None:
                session.add(
                    Term(
                        academic_year_id=year.id,
                        term_type=label,
                        starts_on=date(2025, 9, 1 + i * 110),
                        ends_on=date(2026, 1 + i * 4, 30 + i * 30),
                    )
                )
        session.commit()

    print("Seed data created.")
    print(f"  Demo clerk: demo.clerk / {DEMO_PASSWORD}")
    print(f"  Demo dean : demo.dean / {DEMO_PASSWORD}")
    print(f"  State     : state.admin / {DEMO_PASSWORD}")
    print(f"  Aggregator: aggregator / {DEMO_PASSWORD}")
    print("  Dean signing key: certs/demo_dean_private.pem (dev only)")


def _get_or_create_campus(session, code, name, state_code, mode):
    campus = session.scalar(select(Campus).where(Campus.campus_code == code))
    if campus is None:
        campus = Campus(
            campus_code=code,
            campus_type="secondary" if mode == "campus" else "tertiary",
            name=name,
            state_code=state_code,
            region="Demo Region",
            is_active=True,
        )
        session.add(campus)
        session.flush()
    return campus


def _upsert_campus_user(session, username, role, campus_id):
    user = session.scalar(select(AppUser).where(AppUser.username == username))
    if user is None:
        user = AppUser(
            username=username,
            email=f"{username}@ne-emis.local",
            role=role,
            campus_id=campus_id,
            password_hash=hash_password(DEMO_PASSWORD),
            is_active=True,
        )
        session.add(user)
        session.flush()
    return user


if __name__ == "__main__":
    main()

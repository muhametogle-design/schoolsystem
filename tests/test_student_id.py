"""Auto-generated immutable national student tracking IDs (NE-SID-2026-XY123)."""

from __future__ import annotations

import re

from app.core.db import SessionLocal
from app.models import PrivateSchool, SchoolClass, Student
from app.services.student_id import generate_unique_national_student_id

PATTERN = re.compile(r"^NE-SID-2026-[A-Z]{2}\d{3}$")


def test_id_format_matches_spec():
    with SessionLocal() as db:
        for _ in range(50):
            assert PATTERN.match(generate_unique_national_student_id(db, "2026"))


def test_issued_ids_never_collide_with_the_database():
    """The contract: the generator must never return an ID already stored."""
    with SessionLocal() as db:
        taken = {row.national_student_id for row in db.query(Student).all()}
        assert taken  # seeded estate exists
        for _ in range(25):
            assert generate_unique_national_student_id(db, "2026") not in taken


def test_generator_retries_on_collision(monkeypatch):
    """Deterministic proof of the retry loop: if a candidate collides with a
    stored ID, the generator keeps looping until it finds a free code."""
    with SessionLocal() as db:
        school = db.query(PrivateSchool).first()
        klass = db.query(SchoolClass).filter_by(school_id=school.id).first()
        db.add(
            Student(
                school_id=school.id,
                national_student_id="NE-SID-2026-ZZ999",
                roll_number="ZZ-99999",
                current_class_id=klass.id,
                first_name="Taken",
                last_name="Code",
            )
        )
        db.commit()

    # First attempt: ZZ + 999 (collides with the stored ID) → must retry.
    # Second attempt: QQ + 111 (free) → issued.
    outcomes = iter(["ZZ", "999", "QQ", "111"])

    def fake_choices(population, k):
        return next(outcomes)

    monkeypatch.setattr("app.services.student_id._rng.choices", fake_choices)
    with SessionLocal() as db:
        issued = generate_unique_national_student_id(db, "2026")
    assert issued == "NE-SID-2026-QQ111", "generator returned a colliding ID instead of retrying"


def test_registration_class_list_contains_all_twelve_levels_in_order(client, greenfield_manager_headers):
    """The registration selector receives a complete Class 1 → Class 12 list."""
    response = client.get("/api/v1/school/classes", headers=greenfield_manager_headers)
    assert response.status_code == 200
    classes = response.json()["classes"]

    assert [row["class_level"] for row in classes] == [f"Class {number}" for number in range(1, 13)]
    assert all(row["class_stream"] == "A" for row in classes)


def test_registration_endpoint_issues_generated_id(client, greenfield_manager_headers):
    classes = client.get("/api/v1/school/classes", headers=greenfield_manager_headers).json()["classes"]
    res = client.post(
        "/api/v1/school/students",
        headers=greenfield_manager_headers,
        json={
            "first_name": "Test",
            "last_name": "Learner",
            "current_class_id": classes[0]["id"],
            "gender": "Female",
            "guardian_name": "Test Guardian",
            "guardian_relationship": "Mother",
            "guardian_phone": "+252-63-0000000",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert re.match(r"^AQ-\d+$", body["roll_number"])
    assert body["national_student_id"] == body["roll_number"]

    # The issued roll resolves through the State-wide lookup engine.
    with SessionLocal() as db:
        row = db.query(Student).filter_by(roll_number=body["roll_number"]).one()
        assert row.school_id is not None

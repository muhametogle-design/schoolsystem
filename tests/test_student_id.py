"""Auto-generated immutable national student tracking IDs (STU-2026-XY123)."""

from __future__ import annotations

import re

from app.core.db import SessionLocal
from app.models import Student, StudentGrade  # StudentGrade for __init__ side effects
from app.services.student_id import generate_unique_national_student_id

PATTERN = re.compile(r"^STU-2026-[A-Z]{2}\d{3}$")


def test_id_format_matches_spec():
    with SessionLocal() as db:
        for _ in range(50):
            assert PATTERN.match(generate_unique_national_student_id(db, "2026"))


def test_ids_are_unique_in_a_large_batch():
    with SessionLocal() as db:
        ids = {generate_unique_national_student_id(db, "2026") for _ in range(300)}
        assert len(ids) == 300


def test_registration_endpoint_issues_generated_id(client, greenfield_manager_headers):
    classes = client.get("/api/school/classes", headers=greenfield_manager_headers).json()["classes"]
    res = client.post(
        "/api/school/students",
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
    assert re.match(r"^STU-\d{4}-[A-Z]{2}\d{3}$", body["national_student_id"])

    # The issued ID resolves through the State-wide lookup engine
    with SessionLocal() as db:
        row = db.query(Student).filter_by(national_student_id=body["national_student_id"]).one()
        assert row.school_id is not None

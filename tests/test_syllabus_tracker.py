"""Tests for the syllabus completion tracker (Module 2)."""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models import SchoolClass, Subject, SyllabusPlan


def _headers(client: TestClient, email: str, password: str) -> dict:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _manager(client: TestClient) -> dict:
    return _headers(client, "manager@nugaal.edu.so", "School@2026")


def test_summary_spans_classes_1_to_12_with_status_tags(client, greenfield_manager_token):
    res = client.get(
        "/api/v1/school/syllabus/summary",
        headers={"Authorization": f"Bearer {greenfield_manager_token}"},
    )
    assert res.status_code == 200
    body = res.json()

    levels = {row["class_level"] for row in body["rows"]}
    assert levels == {f"Class {n}" for n in range(1, 13)}

    allowed = {"On Track", "Ahead", "Behind Schedule"}
    for row in body["rows"]:
        assert row["status"] in allowed
        assert 0 <= row["completion_pct"] <= 100
        assert 0 <= row["expected_pct"] <= 100
        assert 0 < row["total_units"]
        assert row["units_completed"] <= row["total_units"]

    assert body["counts"]["On Track"] + body["counts"]["Ahead"] + body["counts"]["Behind Schedule"] == len(body["rows"])
    assert len(body["class_levels_available"]) == 12
    # The deterministic seed must exercise all three status bands.
    assert body["counts"]["Ahead"] > 0
    assert body["counts"]["Behind Schedule"] > 0


def test_class_level_filter(client, greenfield_manager_token):
    res = client.get(
        "/api/v1/school/syllabus/summary?class_level=Class%205",
        headers={"Authorization": f"Bearer {greenfield_manager_token}"},
    )
    assert res.status_code == 200
    rows = res.json()["rows"]
    assert rows and {row["class_level"] for row in rows} == {"Class 5"}


def test_record_progress_updates_completion_and_status(client):
    headers = _manager(client)
    res = client.get("/api/v1/school/syllabus/summary?class_level=Class%203", headers=headers)
    assert res.status_code == 200
    plan = res.json()["rows"][0]
    plan_id = plan["plan_id"]

    record = client.post(
        f"/api/v1/school/syllabus/plans/{plan_id}/progress",
        headers=headers,
        json={"units_after": plan["total_units"], "note": "Rapid catch-up week"},
    )
    assert record.status_code == 201, record.text
    updated = record.json()["plan"]
    assert updated["completion_pct"] == 100.0
    assert updated["status"] == "Ahead"

    # Progress is clamped and audited as a checkpoint history.
    detail = client.get(f"/api/v1/school/syllabus/plans/{plan_id}", headers=headers)
    assert detail.status_code == 200
    entries = detail.json()["entries"]
    assert entries[0]["units_after"] == plan["total_units"]


def test_benchmarks_drive_expected_and_status(client):
    headers = _manager(client)
    res = client.get("/api/v1/school/syllabus/summary?class_level=Class%204", headers=headers)
    plan = res.json()["rows"][0]
    plan_id = plan["plan_id"]

    # Pull the midterm gate to today: the expected percentage must jump.
    update = client.put(
        f"/api/v1/school/syllabus/plans/{plan_id}/benchmarks",
        headers=headers,
        json={"midterm_target_pct": 80, "final_target_pct": 100},
    )
    assert update.status_code == 200, update.text
    after = update.json()["plan"]
    assert after["midterm_target_pct"] == 80
    assert after["expected_pct"] >= plan["expected_pct"]
    assert after["status"] in {"On Track", "Ahead", "Behind Schedule"}


def test_teacher_cannot_set_benchmarks_but_can_record_progress(client):
    teacher = _headers(client, "teacher@nugaal.edu.so", "Teach@2026")
    manager = _manager(client)
    plan_id = client.get(
        "/api/v1/school/syllabus/summary?class_level=Class%206", headers=manager
    ).json()["rows"][0]["plan_id"]

    forbidden = client.put(
        f"/api/v1/school/syllabus/plans/{plan_id}/benchmarks",
        headers=teacher,
        json={"midterm_target_pct": 10},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        f"/api/v1/school/syllabus/plans/{plan_id}/progress",
        headers=teacher,
        json={"units_after": 1},
    )
    assert allowed.status_code == 201


def test_create_plan_and_duplicate_guard(client):
    headers = _manager(client)
    with SessionLocal() as db:
        klass = db.query(SchoolClass).filter_by(school_id=3, class_level="Class 8").first()
        subject = (
            db.query(Subject)
            .filter_by(school_id=3, class_level="Class 8")
            .filter(Subject.subject_code.startswith("MAT"))
            .first()
        )
        assert klass and subject

    created = client.post(
        "/api/v1/school/syllabus/plans",
        headers=headers,
        json={
            "class_id": klass.id,
            "subject_id": subject.id,
            "term": "Term 2",
            "total_units": 20,
            "midterm_target_pct": 50,
            "final_target_pct": 100,
        },
    )
    assert created.status_code == 201, created.text
    plan = created.json()["plan"]
    assert plan["total_units"] == 20
    assert plan["term"] == "Term 2"
    assert plan["term_start"] and plan["midterm_date"] and plan["term_end"]

    duplicate = client.post(
        "/api/v1/school/syllabus/plans",
        headers=headers,
        json={
            "class_id": klass.id,
            "subject_id": subject.id,
            "term": "Term 2",
            "total_units": 18,
        },
    )
    assert duplicate.status_code == 409


def test_state_role_firewalled(client, state_token):
    res = client.get(
        "/api/v1/school/syllabus/summary", headers={"Authorization": f"Bearer {state_token}"}
    )
    assert res.status_code == 403

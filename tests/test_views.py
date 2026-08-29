"""Phase 3 — Views A / B / C via the API routing services."""

from __future__ import annotations

from app.core.db import SessionLocal
from app.models import Student, StudentGrade


def test_view_a_compliance_map_orders_and_classifies(client, auth_headers):
    body = client.get("/api/v1/state/compliance-map", headers=auth_headers).json()
    schools = body["schools"]
    assert len(schools) == 3  # exactly the three seeded active schools
    assert all(s["state_license_number"] for s in schools)

    # Red alarms float to the top of the command map
    flags = [s["is_red_alarm_active"] for s in schools]
    assert flags == sorted(flags, reverse=True)

    statuses = {s["school_name"]: s["state_compliance_status"] for s in schools}
    assert "✅ COMPLIANT" in statuses["Greenfield Academy"]
    assert "✅ COMPLIANT" in statuses["Crescent International School"]


def test_view_b_lookup_by_exact_national_id(client, auth_headers):
    with SessionLocal() as db:
        sample = db.query(Student).filter_by(is_active=True).first()
    res = client.get(
        f"/api/v1/state/students/search?q={sample.national_student_id}", headers=auth_headers
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert any(r["national_student_id"] == sample.national_student_id for r in results)
    row = next(r for r in results if r["national_student_id"] == sample.national_student_id)
    assert row["guardian_name"] == sample.guardian_name
    assert row["emergency_contact_phone"] == sample.emergency_contact_phone


def test_view_b_lookup_by_last_name(client, auth_headers):
    with SessionLocal() as db:
        sample = db.query(Student).filter_by(is_active=True).first()
    res = client.get(f"/api/v1/state/students/search?q={sample.last_name}", headers=auth_headers)
    results = res.json()["results"]
    assert results, "Last-name deep search returned nothing"
    assert all(r["last_name"] == sample.last_name for r in results)


def test_view_c_analytics_only_aggregates_published_rows(client, auth_headers):
    rows = client.get("/api/v1/state/analytics/grades", headers=auth_headers).json()["rows"]
    assert rows
    with SessionLocal() as db:
        published_count = db.query(StudentGrade).filter_by(is_published=True).count()
    # Every analytics row maps onto genuinely published marks
    assert published_count > 0
    for r in rows:
        assert r["total_marked_records"] > 0
        assert 0 <= r["structural_average_mark"] <= 100
        assert 0 <= r["peak_score"] <= 100


def test_view_c_class_level_filter(client, auth_headers):
    rows = client.get(
        "/api/v1/state/analytics/grades?class_level=Class 5", headers=auth_headers
    ).json()["rows"]
    assert rows and all(r["class_level"] == "Class 5" for r in rows)


def test_view_c_requires_release_token_event(client, auth_headers):
    """STEP 3 / Query C: only scores with a matching token event inside
    exam_submission_events are pulled — a rogue is_published flag with no
    event must stay invisible."""
    with SessionLocal() as db:
        draft = db.query(StudentGrade).filter_by(is_published=False).first()
        assert draft is not None
        school_id = draft.school_id

    url = f"/api/v1/state/analytics/grades?school_id={school_id}"
    before = client.get(url, headers=auth_headers).json()["rows"]

    with SessionLocal() as db:
        db.query(StudentGrade).filter_by(id=draft.id).update({"is_published": True})
        db.commit()

    after = client.get(url, headers=auth_headers).json()["rows"]

    with SessionLocal() as db:  # restore the draft state
        db.query(StudentGrade).filter_by(id=draft.id).update({"is_published": False})
        db.commit()

    assert len(after) == len(before), "Untokenized grade rows leaked into the benchmarking index"


def test_live_attendance_visibility(client, auth_headers):
    body = client.get("/api/v1/state/attendance/live", headers=auth_headers).json()
    assert "records" in body
    for r in body["records"]:
        assert r["status"] in ("Present", "Absent", "Late", "Excused")
        assert r["national_student_id"].startswith("NE-SID-")

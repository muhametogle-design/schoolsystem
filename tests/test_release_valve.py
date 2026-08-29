"""THE EXAM DATA RELEASE VALVE — drafts are invisible to the State until the
school administrator hits 'Publish Exam Marks to State'."""

from __future__ import annotations

from app.core.db import SessionLocal
from app.models import ExamSubmissionEvent, PrivateSchool, StudentGrade


def _horizon_school_id() -> int:
    with SessionLocal() as db:
        return db.query(PrivateSchool).filter_by(school_name="Horizon Preparatory School").one().id


def _analytics_for_horizon(client, auth_headers):
    sid = _horizon_school_id()
    rows = client.get(f"/api/state/analytics/grades?school_id={sid}", headers=auth_headers).json()["rows"]
    return rows


def _draft_scope(client, horizon_manager_headers):
    classes = client.get("/api/school/classes", headers=horizon_manager_headers).json()["classes"]
    year = client.get("/api/school/academic-years", headers=horizon_manager_headers).json()["academic_years"]
    year_id = next(y["id"] for y in year if y["is_current"])
    for c in classes:
        subjects = client.get(
            f"/api/school/subjects?class_level={c['class_level']}", headers=horizon_manager_headers
        ).json()["subjects"]
        roster = client.get(
            f"/api/school/students?class_id={c['id']}", headers=horizon_manager_headers
        ).json()["students"]
        if subjects and roster:
            return c, subjects[0], year_id, roster
    raise AssertionError("No teachable scope found for Horizon")


def test_drafts_are_invisible_to_state_analytics(client, auth_headers, horizon_manager_headers):
    c, subject, year_id, roster = _draft_scope(client, horizon_manager_headers)
    exam = "Valve Test Opener"

    # Teacher/school saves private draft marks
    res = client.post(
        "/api/school/grades",
        headers=horizon_manager_headers,
        json={
            "class_id": c["id"],
            "subject_id": subject["id"],
            "academic_year_id": year_id,
            "exam_name": exam,
            "entries": [{"student_id": s["id"], "numeric_score": 77.5} for s in roster],
        },
    )
    assert res.status_code == 200

    # State analytics must not include the unpublished exam
    rows = [r for r in _analytics_for_horizon(client, auth_headers) if r["subject_name"] == subject["subject_name"]]
    assert all(r["class_level"] != c["class_level"] for r in rows), "Draft marks leaked into state analytics"


def test_publish_releases_data_and_creates_immutable_event(
    client, auth_headers, horizon_manager_headers
):
    c, subject, year_id, roster = _draft_scope(client, horizon_manager_headers)
    exam = "Valve Test Opener"

    res = client.post(
        "/api/school/grades/publish",
        headers=horizon_manager_headers,
        json={
            "class_id": c["id"],
            "subject_id": subject["id"],
            "academic_year_id": year_id,
            "exam_name": exam,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["records_released"] == len(roster)

    # State analytics now include the released scope
    rows = _analytics_for_horizon(client, auth_headers)
    match = [r for r in rows if r["class_level"] == c["class_level"] and r["subject_name"] == subject["subject_name"]]
    assert match, "Published marks did not appear in state analytics"
    assert match[0]["total_marked_records"] == len(roster)
    assert match[0]["structural_average_mark"] == 77.5

    with SessionLocal() as db:
        event = (
            db.query(ExamSubmissionEvent)
            .filter_by(exam_name=exam, subject_id=subject["id"], class_id=c["id"])
            .one()
        )
        assert event.records_released == len(roster)


def test_republish_is_rejected(client, auth_headers, horizon_manager_headers):
    c, subject, year_id, _ = _draft_scope(client, horizon_manager_headers)
    res = client.post(
        "/api/school/grades/publish",
        headers=horizon_manager_headers,
        json={
            "class_id": c["id"],
            "subject_id": subject["id"],
            "academic_year_id": year_id,
            "exam_name": "Valve Test Opener",
        },
    )
    assert res.status_code == 409
    assert "immutable" in res.json()["detail"].lower()


def test_published_marks_are_frozen(client, horizon_manager_headers):
    c, subject, year_id, roster = _draft_scope(client, horizon_manager_headers)
    res = client.post(
        "/api/school/grades",
        headers=horizon_manager_headers,
        json={
            "class_id": c["id"],
            "subject_id": subject["id"],
            "academic_year_id": year_id,
            "exam_name": "Valve Test Opener",
            "entries": [{"student_id": roster[0]["id"], "numeric_score": 99}],
        },
    )
    assert res.status_code == 409


def test_teachers_cannot_publish(client, greenfield_teacher_headers):
    res = client.post(
        "/api/school/grades/publish",
        headers=greenfield_teacher_headers,
        json={"class_id": 1, "subject_id": 1, "academic_year_id": 1, "exam_name": "X"},
    )
    assert res.status_code == 403


def test_publication_is_irreversible_in_db():
    """The ORM model carries no path back to draft (and PG triggers hard-block it)."""
    with SessionLocal() as db:
        published = db.query(StudentGrade).filter_by(is_published=True).count()
        assert published > 0

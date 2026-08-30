"""Regression contracts for the complete multi-tenant school architecture."""

from __future__ import annotations

import re

from app.core.db import SessionLocal
from app.models import PrivateSchool, SchoolClass, SchoolRollSequence, Subject, TeachingAssignment, User

EXPECTED_SCHOOLS = {
    "Ilays Educational Academy": "IL",
    "Muse Yusuf Secondary School": "MY",
    "Nugaal High School": "NG",
    "ALQALAM SCHOOLS": "AQ",
    "Las Anod Boarding Secondary School (LBSS)": "LB",
}
CORE_SUBJECTS = {
    "Somali (Af-Somali)", "Arabic", "English", "Mathematics", "Islamic Studies",
    "Physics", "Chemistry", "Biology", "History", "Geography",
}


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_initial_seed_is_exact_requested_five_school_estate(client):
    with SessionLocal() as db:
        schools = db.query(PrivateSchool).order_by(PrivateSchool.school_name).all()
        assert {school.school_name: school.school_code for school in schools} == EXPECTED_SCHOOLS
        for school in schools:
            teachers = db.query(User).filter_by(school_id=school.id, role="teacher", is_active=True).count()
            subjects = db.query(Subject).filter_by(school_id=school.id).all()
            classes = db.query(SchoolClass).filter_by(school_id=school.id).all()
            assignments = db.query(TeachingAssignment).filter_by(school_id=school.id).all()
            assert teachers >= 8
            assert len(subjects) == 12 * 10
            assert {subject.subject_name for subject in subjects} >= CORE_SUBJECTS
            assert len(assignments) == len(classes) * 10
            assert all(assignment.teacher_id is not None for assignment in assignments)
            assert db.get(SchoolRollSequence, school.id).next_value >= 10000


def test_registration_uses_sequential_school_code_roll_numbers(client):
    manager_headers = _login(client, "manager@nugaal.edu.so", "School@2026")
    admin_headers = _login(client, "stateadmin@education.gov", "StateAdmin@2026")
    classes = client.get("/api/v1/school/classes", headers=manager_headers).json()["classes"]
    with SessionLocal() as db:
        nugaal_id = db.query(PrivateSchool.id).filter_by(school_code="NG").scalar()
    before = client.get(f"/api/v1/state/schools/{nugaal_id}/roll-sequence", headers=admin_headers)
    assert before.status_code == 200
    next_value = before.json()["next_value"]

    response = client.post(
        "/api/v1/school/students",
        headers=manager_headers,
        json={"first_name": "Sequential", "last_name": "Roll", "current_class_id": classes[0]["id"]},
    )
    assert response.status_code == 201, response.text
    student = response.json()
    assert student["roll_number"] == f"NG-{next_value}"
    assert student["national_student_id"] == student["roll_number"]
    assert re.fullmatch(r"NG-\d+", student["roll_number"])

    after = client.get(f"/api/v1/state/schools/{nugaal_id}/roll-sequence", headers=admin_headers).json()
    assert after["next_value"] == next_value + 1


def test_inspector_can_read_class_breakdown_but_cannot_provision_school(client):
    inspector_headers = _login(client, "inspector@education.gov", "State@2026")
    with SessionLocal() as db:
        nugaal = db.query(PrivateSchool).filter_by(school_code="NG").one()
        klass = db.query(SchoolClass).filter_by(school_id=nugaal.id, class_level="Class 1", class_stream="A").one()

    breakdown = client.get(
        f"/api/v1/state/institutions/{nugaal.id}/classes/{klass.id}/breakdown",
        headers=inspector_headers,
    )
    assert breakdown.status_code == 200
    payload = breakdown.json()
    assert payload["school"]["school_code"] == "NG"
    assert len(payload["subjects"]) == 10
    assert all(row["teacher"] for row in payload["subjects"])
    assert all(row["roll_number"].startswith("NG-") for row in payload["students"])

    denied = client.post("/api/v1/state/schools", headers=inspector_headers, json={})
    assert denied.status_code == 403
    assert client.patch(
        f"/api/v1/state/schools/{nugaal.id}", headers=inspector_headers, json={}
    ).status_code == 403

    teacher_headers = _login(client, "teacher@nugaal.edu.so", "Teach@2026")
    teacher_registration = client.post(
        "/api/v1/school/students",
        headers=teacher_headers,
        json={"first_name": "Not", "last_name": "Allowed", "current_class_id": klass.id},
    )
    assert teacher_registration.status_code == 403


def test_state_admin_provisions_complete_new_tenant_then_cleanup(client, state_admin_headers):
    response = client.post(
        "/api/v1/state/schools",
        headers=state_admin_headers,
        json={
            "school_name": "Future Learning Academy",
            "state_license_number": "SOL/PS/2026/FL99",
            "school_code": "FL",
            "manager_first_name": "Future",
            "manager_last_name": "Principal",
            "manager_email": "principal@future-learning.example",
            "manager_password": "StrongPass2026",
            "streams": ["A", "B"],
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["school_code"] == "FL"
    assert created["template"]["classes_created"] == 24
    assert created["template"]["subjects_created"] == 120
    assert created["template"]["teachers_created"] == 8
    assert created["template"]["teacher_assignments_created"] == 240

    school_id = created["id"]
    state_token = state_admin_headers["Authorization"].split(" ", 1)[1]
    # State dashboards receive a safe academic-structure event as soon as a
    # school identity update commits; no finance fields enter the event bus.
    with client.websocket_connect(f"/ws?token={state_token}") as ws:
        assert ws.receive_json()["type"] == "connected"
        updated_identity = client.patch(
            f"/api/v1/state/schools/{school_id}",
            headers=state_admin_headers,
            json={"contact_phone": "+252-63-400-9999", "accreditation_status": "Active"},
        )
        assert updated_identity.status_code == 200
        event = ws.receive_json()
        assert event["type"] == "academic_structure_changed"
        assert event["payload"]["school_id"] == school_id
        assert "billing" not in event["payload"]
    assert updated_identity.json()["school_code"] == "FL"
    forbidden_billing = client.patch(
        f"/api/v1/state/schools/{school_id}",
        headers=state_admin_headers,
        json={"billing_email": "state-must-not-set-this@example.test"},
    )
    assert forbidden_billing.status_code == 422

    classes = client.get(f"/api/v1/state/institutions/{school_id}/classes", headers=state_admin_headers).json()["classes"]
    assert len(classes) == 24
    class_breakdown = client.get(
        f"/api/v1/state/institutions/{school_id}/classes/{classes[0]['id']}/breakdown",
        headers=state_admin_headers,
    ).json()
    assert len(class_breakdown["subjects"]) == 10
    assert all(row["teacher"] for row in class_breakdown["subjects"])

    # This test suite uses one shared SQLite database. Remove the temporary
    # tenant so count-sensitive initial-data tests retain their exact contract.
    with SessionLocal() as db:
        school = db.get(PrivateSchool, school_id)
        db.delete(school)
        db.commit()


def test_school_manager_can_manage_teacher_and_mapping(client, greenfield_manager_headers):
    created = client.post(
        "/api/v1/school/teachers",
        headers=greenfield_manager_headers,
        json={
            "first_name": "New",
            "last_name": "Faculty",
            "email": "new.faculty@alqalam.example",
            "password": "TeacherPass2026",
            "designation": "Science Teacher",
        },
    )
    assert created.status_code == 201, created.text
    teacher = created.json()["teacher"]

    classes = client.get("/api/v1/school/classes", headers=greenfield_manager_headers).json()["classes"]
    breakdown = client.get(
        f"/api/v1/school/classes/{classes[0]['id']}/breakdown", headers=greenfield_manager_headers
    ).json()
    assignment = client.put(
        f"/api/v1/school/classes/{classes[0]['id']}/subjects/{breakdown['subjects'][0]['id']}/assignment",
        headers=greenfield_manager_headers,
        json={"teacher_id": teacher["id"]},
    )
    assert assignment.status_code == 200, assignment.text

    profile = client.get(f"/api/v1/school/teachers/{teacher['id']}", headers=greenfield_manager_headers)
    assert profile.status_code == 200
    assert profile.json()["teacher"]["assignments"]

    removed = client.delete(f"/api/v1/school/teachers/{teacher['id']}", headers=greenfield_manager_headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["assignments_reassigned"] >= 1
    updated = client.get(
        f"/api/v1/school/classes/{classes[0]['id']}/breakdown", headers=greenfield_manager_headers
    ).json()
    # Removing staff preserves the complete mandatory curriculum: assignments
    # are moved to a remaining active teacher instead of becoming vacant.
    assert all(row["teacher"] is not None for row in updated["subjects"])
    assert all(row["teacher"]["id"] != teacher["id"] for row in updated["subjects"])

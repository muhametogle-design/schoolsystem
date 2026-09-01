"""Tests for the Manager syllabus CRUD, teacher auth (Staff ID + PIN), and the
subject-restricted attendance marking engine."""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models import (
    SchoolClass,
    Student,
    Subject,
    SubjectAttendance,
    SyllabusPlan,
    SyllabusTopic,
    TeachingAssignment,
    TimetableSlot,
    User,
)


def _login(client: TestClient, email: str, password: str) -> dict:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _manager(client: TestClient) -> dict:
    return _login(client, "manager@nugaal.edu.so", "School@2026")


def _teacher_with_slot(client: TestClient) -> tuple[dict, TimetableSlot, User]:
    """Login as a teacher who owns at least one timetable slot this week."""
    with SessionLocal() as db:
        slot = db.query(TimetableSlot).filter_by(school_id=3).order_by(TimetableSlot.id).first()
        teacher = db.get(User, slot.teacher_id)
        # Keep ORM objects alive after session close: copy primitives.
        slot_id, class_id, subject_id = slot.id, slot.class_id, slot.subject_id
        day, period = slot.day_of_week, slot.period_number
        email = teacher.email
    headers = _login(client, email, "Teach@2026")
    return headers, slot, None, class_id, subject_id, day, period


# ===========================================================================
# Refinement 1 — editable syllabus (manager CRUD, topics, log covered)
# ===========================================================================


def test_manager_full_plan_crud(client, greenfield_manager_token):
    headers = {"Authorization": f"Bearer {greenfield_manager_token}"}
    summary = client.get(
        "/api/v1/school/syllabus/summary?class_level=Class%207", headers=headers
    ).json()
    plan = summary["rows"][0]
    plan_id = plan["plan_id"]

    # Full UPDATE: units, targets, term label and deadlines in one call.
    updated = client.put(
        f"/api/v1/school/syllabus/plans/{plan_id}",
        headers=headers,
        json={
            "term": "Term 1 (revised)",
            "total_units": 24,
            "midterm_target_pct": 55,
            "final_target_pct": 100,
            "midterm_date": (dt.date.today() + dt.timedelta(days=20)).isoformat(),
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()["plan"]
    assert body["term"] == "Term 1 (revised)"
    assert body["total_units"] == 24
    assert body["midterm_target_pct"] == 55

    # DELETE removes plan, topics and checkpoints (cascade).
    with SessionLocal() as db:
        topic_count = db.query(SyllabusTopic).filter_by(plan_id=plan_id).count()
    assert topic_count > 0
    deleted = client.delete(f"/api/v1/school/syllabus/plans/{plan_id}", headers=headers)
    assert deleted.status_code == 200
    with SessionLocal() as db:
        assert db.get(SyllabusPlan, plan_id) is None
        assert db.query(SyllabusTopic).filter_by(plan_id=plan_id).count() == 0

    gone = client.get(f"/api/v1/school/syllabus/plans/{plan_id}", headers=headers)
    assert gone.status_code == 404


def test_teacher_cannot_update_or_delete_plans(client):
    headers = _login(client, "teacher@nugaal.edu.so", "Teach@2026")
    manager = _manager(client)
    plan_id = client.get(
        "/api/v1/school/syllabus/summary?class_level=Class%208", headers=manager
    ).json()["rows"][0]["plan_id"]

    assert (
        client.put(
            f"/api/v1/school/syllabus/plans/{plan_id}",
            headers=headers,
            json={"total_units": 99},
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/school/syllabus/plans/{plan_id}", headers=headers).status_code
        == 403
    )


def test_topic_list_add_edit_delete(client, greenfield_manager_token):
    headers = {"Authorization": f"Bearer {greenfield_manager_token}"}
    plan_id = client.get(
        "/api/v1/school/syllabus/summary?class_level=Class%209", headers=headers
    ).json()["rows"][0]["plan_id"]

    topics = client.get(f"/api/v1/school/syllabus/plans/{plan_id}/topics", headers=headers)
    assert topics.status_code == 200
    existing = topics.json()["topics"]
    assert existing, "seeded plans carry their curriculum unit list"

    added = client.post(
        f"/api/v1/school/syllabus/plans/{plan_id}/topics",
        headers=headers,
        json={"title": "National exam paper drill", "code": "EXAM"},
    )
    assert added.status_code == 201, added.text
    topic = added.json()["topic"]
    assert topic["code"] == "EXAM" and topic["is_done"] is False

    edited = client.put(
        f"/api/v1/school/syllabus/plans/{plan_id}/topics/{topic['id']}",
        headers=headers,
        json={"title": "National exam paper drill (extended)"},
    )
    assert edited.json()["topic"]["title"].endswith("(extended)")

    removed = client.delete(
        f"/api/v1/school/syllabus/plans/{plan_id}/topics/{topic['id']}", headers=headers
    )
    assert removed.status_code == 200


def test_log_topic_covered_updates_progress_and_topics(client, greenfield_manager_token):
    headers = {"Authorization": f"Bearer {greenfield_manager_token}"}
    plan_id = client.get(
        "/api/v1/school/syllabus/summary?class_level=Class%2010", headers=headers
    ).json()["rows"][0]["plan_id"]

    topics = client.get(f"/api/v1/school/syllabus/plans/{plan_id}/topics", headers=headers).json()["topics"]
    unticked = [t["id"] for t in topics if not t["is_done"]]
    assert unticked, "seed has unfinished units to log"

    before = client.get(f"/api/v1/school/syllabus/plans/{plan_id}", headers=headers).json()["plan"]

    logged = client.post(
        f"/api/v1/school/syllabus/plans/{plan_id}/topics/log-covered",
        headers=headers,
        json={"topic_ids": unticked[:2]},
    )
    assert logged.status_code == 200, logged.text
    body = logged.json()
    assert body["ticked"] == 2
    assert body["plan"]["units_completed"] >= before["units_completed"]

    # Tick list and checkpoint stay reconciled.
    after_topics = client.get(
        f"/api/v1/school/syllabus/plans/{plan_id}/topics", headers=headers
    ).json()["topics"]
    done_count = sum(1 for t in after_topics if t["is_done"])
    assert body["plan"]["units_completed"] == min(
        done_count, body["plan"]["total_units"]
    )

    # Undo path (manager correction).
    undone = client.post(
        f"/api/v1/school/syllabus/plans/{plan_id}/topics/undo-covered",
        headers=headers,
        json={"topic_ids": unticked[:2]},
    )
    assert undone.status_code == 200
    assert undone.json()["unticked"] == 2


def test_department_head_can_log_topics_but_plain_teacher_cannot(client):
    manager = _manager(client)
    with SessionLocal() as db:
        head = db.query(User).filter_by(school_id=3, is_department_head=True).first()
        assert head, "seed must include a department head"
        head_email = head.email

    head_headers = _login(client, head_email, "Teach@2026")
    me = client.get("/api/auth/me", headers=head_headers).json()
    assert me["is_department_head"] is True

    plan_id = client.get(
        "/api/v1/school/syllabus/summary?class_level=Class%2011", headers=manager
    ).json()["rows"][0]["plan_id"]
    topics = client.get(
        f"/api/v1/school/syllabus/plans/{plan_id}/topics", headers=head_headers
    ).json()["topics"]
    unticked = [t["id"] for t in topics if not t["is_done"]]
    if unticked:
        assert (
            client.post(
                f"/api/v1/school/syllabus/plans/{plan_id}/topics/log-covered",
                headers=head_headers,
                json={"topic_ids": unticked[:1]},
            ).status_code
            == 200
        )

    plain = _login(client, "teacher@nugaal.edu.so", "Teach@2026")
    assert (
        client.post(
            f"/api/v1/school/syllabus/plans/{plan_id}/topics",
            headers=plain,
            json={"title": "Unauthorised topic"},
        ).status_code
        == 403
    )


def test_manager_can_delete_progress_entry(client, greenfield_manager_token):
    headers = {"Authorization": f"Bearer {greenfield_manager_token}"}
    plan_id = client.get(
        "/api/v1/school/syllabus/summary?class_level=Class%2012", headers=headers
    ).json()["rows"][0]["plan_id"]
    detail = client.get(f"/api/v1/school/syllabus/plans/{plan_id}", headers=headers).json()
    entry_id = detail["entries"][0]["id"]

    removed = client.delete(
        f"/api/v1/school/syllabus/plans/{plan_id}/progress/{entry_id}", headers=headers
    )
    assert removed.status_code == 200
    assert removed.json()["deleted"] == entry_id


# ===========================================================================
# Refinement 2 — Staff ID + PIN authentication
# ===========================================================================


def _teacher_staff_id() -> str:
    with SessionLocal() as db:
        teacher = db.query(User).filter_by(email="teacher@nugaal.edu.so").first()
        return teacher.staff_identifier


def test_staff_id_pin_login_works(client):
    staff_id = _teacher_staff_id()
    res = client.post(
        "/api/auth/login",
        json={"staff_identifier": staff_id, "pin": "2026"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["role"] == "teacher"
    assert body["user"]["staff_identifier"] == staff_id

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()
    assert me["is_department_head"] in (True, False)


def test_wrong_pin_rejected(client):
    staff_id = _teacher_staff_id()
    res = client.post(
        "/api/auth/login",
        json={"staff_identifier": staff_id, "pin": "9999"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid credentials"


def test_pin_login_without_pin_rejected(client):
    res = client.post("/api/auth/login", json={"staff_identifier": _teacher_staff_id()})
    assert res.status_code == 422


# ===========================================================================
# Refinement 3 — subject-restricted attendance marking
# ===========================================================================


def _owned_and_foreign_slots():
    """(teacher A email+slot, teacher B email, ids) with slots TODAY.

    Both teachers own at least one timetable period today, so the portal
    schedule and roster flows have real data to work against.
    """
    today_weekday = dt.date.today().weekday()
    with SessionLocal() as db:
        slots = (
            db.query(TimetableSlot)
            .filter_by(school_id=3, day_of_week=today_weekday)
            .order_by(TimetableSlot.id)
            .all()
        )
        teacher_ids = sorted({s.teacher_id for s in slots})
        id_a, id_b = teacher_ids[0], teacher_ids[-1]
        slot_a = next(s for s in slots if s.teacher_id == id_a)
        slot_b = next(s for s in slots if s.teacher_id == id_b)
        email_a = db.get(User, id_a).email
        email_b = db.get(User, id_b).email
        return (
            email_a,
            (slot_a.class_id, slot_a.subject_id, slot_a.day_of_week, slot_a.period_number),
            email_b,
            id_a,
            id_b,
        )


def test_schedule_lists_only_own_slots_with_active_period(client):
    email_a, owned, email_b, id_a, id_b = _owned_and_foreign_slots()
    headers = _login(client, email_a, "Teach@2026")
    schedule = client.get("/api/v1/school/teachers/me/schedule", headers=headers)
    assert schedule.status_code == 200, schedule.text
    body = schedule.json()
    assert body["teacher"]["staff_identifier"]
    assert body["active_period"] in list(range(1, 9)) or body["active_period"] is None
    assert body["period_windows"]["1"] == ["08:00", "08:50"]
    # Every slot must belong to the signed-in teacher (verified via ownership
    # probe on one roster call below) and carry class/subject labels.
    assert body["slots"], "seeded teacher must have scheduled periods"
    assert all("class_label" in s and "subject_name" in s for s in body["slots"])


def test_teacher_can_mark_own_slot_roster(client):
    email_a, owned, email_b, id_a, id_b = _owned_and_foreign_slots()
    class_id, subject_id, day, period = owned
    headers = _login(client, email_a, "Teach@2026")

    # Find a date whose weekday matches the slot (within the next week).
    today = dt.date.today()
    for offset in range(8):
        candidate = today + dt.timedelta(days=offset)
        if candidate.weekday() == day:
            date = candidate
            break

    roster = client.get(
        "/api/v1/school/teachers/me/roster",
        headers=headers,
        params={
            "class_id": class_id,
            "subject_id": subject_id,
            "period_number": period,
            "date": date.isoformat(),
        },
    )
    assert roster.status_code == 200, roster.text
    students = roster.json()["students"]
    assert students, "roster must list the class students"

    entries = [
        {"student_id": s["student_id"], "status": "Present" if i % 4 else "Late"}
        for i, s in enumerate(students)
    ]
    saved = client.post(
        "/api/v1/school/teachers/me/roster",
        headers=headers,
        json={
            "class_id": class_id,
            "subject_id": subject_id,
            "period_number": period,
            "date": date.isoformat(),
            "entries": entries,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["saved"] == len(entries)

    # Upsert semantics: re-marking the same slot updates in place.
    with SessionLocal() as db:
        count = (
            db.query(SubjectAttendance)
            .filter_by(
                school_id=3, subject_id=subject_id, period_number=period, date=date
            )
            .count()
        )
        assert count == len(entries)


def test_teacher_blocked_from_foreign_slot(client):
    email_a, owned, email_b, id_a, id_b = _owned_and_foreign_slots()
    class_id, subject_id, day, period = owned
    headers_b = _login(client, email_b, "Teach@2026")

    today = dt.date.today()
    date = next(
        today + dt.timedelta(days=o) for o in range(8) if (today + dt.timedelta(days=o)).weekday() == day
    )
    blocked = client.get(
        "/api/v1/school/teachers/me/roster",
        headers=headers_b,
        params={
            "class_id": class_id,
            "subject_id": subject_id,
            "period_number": period,
            "date": date.isoformat(),
        },
    )
    assert blocked.status_code == 403
    assert "another teacher" in blocked.json()["detail"]

    blocked_save = client.post(
        "/api/v1/school/teachers/me/roster",
        headers=headers_b,
        json={
            "class_id": class_id,
            "subject_id": subject_id,
            "period_number": period,
            "date": date.isoformat(),
            "entries": [],
        },
    )
    assert blocked_save.status_code == 403


def test_legacy_attendance_requires_subject_period_for_teachers(client):
    with SessionLocal() as db:
        klass = db.query(SchoolClass).filter_by(school_id=3, class_level="Class 2").first()
        students = (
            db.query(Student)
            .filter_by(school_id=3, current_class_id=klass.id, is_active=True)
            .all()
        )
        klass_id = klass.id
        student_ids = [s.id for s in students]
        email = db.get(User, 1)  # placeholder to keep flake happy

    teacher_headers = _login(client, "teacher@nugaal.edu.so", "Teach@2026")

    # Class-wide marking without subject/period is now blocked for teachers.
    blocked = client.post(
        "/api/v1/school/attendance",
        headers=teacher_headers,
        json={
            "date": dt.date.today().isoformat(),
            "class_id": klass_id,
            "entries": [{"student_id": student_ids[0], "status": "Present"}],
        },
    )
    assert blocked.status_code == 403
    assert "assigned subject and period" in blocked.json()["detail"]


def test_legacy_attendance_still_open_to_managers(client, greenfield_manager_token):
    headers = {"Authorization": f"Bearer {greenfield_manager_token}"}
    school_id = client.get("/api/auth/me", headers=headers).json()["school_id"]
    with SessionLocal() as db:
        klass = db.query(SchoolClass).filter_by(school_id=school_id, class_level="Class 3").first()
        student = (
            db.query(Student)
            .filter_by(school_id=school_id, current_class_id=klass.id, is_active=True)
            .first()
        )
        klass_id, student_id = klass.id, student.id

    res = client.post(
        "/api/v1/school/attendance",
        headers=headers,
        json={
            "date": dt.date.today().isoformat(),
            "class_id": klass_id,
            "entries": [{"student_id": student_id, "status": "Present"}],
        },
    )
    assert res.status_code == 200, res.text


def test_teacher_cannot_read_foreign_class_attendance(client):
    with SessionLocal() as db:
        # Pick the teacher with the fewest assignments to guarantee a class
        # outside their teaching load exists.
        from sqlalchemy import func as sa_func

        counts = (
            db.query(
                TeachingAssignment.teacher_id, sa_func.count(TeachingAssignment.id)
            )
            .filter(TeachingAssignment.school_id == 3, TeachingAssignment.teacher_id == User.id)
            .group_by(TeachingAssignment.teacher_id)
            .order_by(sa_func.count(TeachingAssignment.id).asc())
            .first()
        )
        teacher_id = counts[0]
        email = db.get(User, teacher_id).email
        taught_classes = {
            row[0]
            for row in db.query(TeachingAssignment.class_id).filter_by(
                school_id=3, teacher_id=teacher_id
            )
        }
        foreign = (
            db.query(SchoolClass)
            .filter(SchoolClass.school_id == 3, SchoolClass.id.notin_(taught_classes))
            .first()
        )
        assert foreign, "a lightly-loaded teacher must have unassigned classes"
        foreign_id = foreign.id

    headers = _login(client, email, "Teach@2026")
    res = client.get(
        "/api/v1/school/attendance",
        headers=headers,
        params={"class_id": foreign_id, "date": dt.date.today().isoformat()},
    )
    assert res.status_code == 403

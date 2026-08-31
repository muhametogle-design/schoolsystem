"""Tests for the teacher absence & substitution engine (Module 1)."""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import (
    SchoolClass,
    Subject,
    TeacherAbsence,
    TimetableSlot,
    User,
)


def _school_user_headers(client: TestClient) -> dict:
    res = client.post(
        "/api/auth/login",
        json={"email": "manager@nugaal.edu.so", "password": "School@2026"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _teacher_ids(client: TestClient, headers: dict) -> list[dict]:
    res = client.get("/api/v1/school/teachers", headers=headers)
    assert res.status_code == 200
    return res.json()["teachers"]


def test_timetable_exists_and_is_conflict_free(client, greenfield_manager_token):
    res = client.get("/api/v1/school/timetable", headers={"Authorization": f"Bearer {greenfield_manager_token}"})
    assert res.status_code == 200
    slots = res.json()["slots"]
    assert len(slots) > 100  # every class carries a two-periods-per-day week

    seen_teacher, seen_class = set(), set()
    for slot in slots:
        key_t = (slot["teacher_id"], slot["day_of_week"], slot["period_number"])
        key_c = (slot["class_id"], slot["day_of_week"], slot["period_number"])
        assert key_t not in seen_teacher, "teacher double-booked"
        assert key_c not in seen_class, "class double-booked"
        seen_teacher.add(key_t)
        seen_class.add(key_c)


def test_logging_absence_returns_ranked_coverage_panel(client):
    headers = _school_user_headers(client)
    today = dt.date.today()

    with SessionLocal() as db:
        slots = (
            db.query(TimetableSlot)
            .filter(TimetableSlot.school_id == 3, TimetableSlot.day_of_week == today.weekday())
            .all()
        )
        assert slots, "seeded timetable must have slots today"
        already_absent = {
            a.teacher_id
            for a in db.query(TeacherAbsence).filter_by(school_id=3, absence_date=today)
        }
        teacher_id = next(s.teacher_id for s in slots if s.teacher_id not in already_absent)

    res = client.post(
        "/api/v1/school/absences",
        headers=headers,
        json={"teacher_id": teacher_id, "absence_date": today.isoformat(), "reason": "Sick leave"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    panel = body["panel"]
    assert panel["teacher_id"] == teacher_id
    assert panel["slots_total"] >= 1
    assert panel["slots_uncovered"] == panel["slots_total"]

    absent_ids = {teacher_id}
    for slot in panel["slots"]:
        assert slot["candidates"], "engine must find candidates for every slot"
        top = slot["candidates"][0]
        assert top["teacher_id"] not in absent_ids
        assert top["score"] > 0
        assert top["reasons"], "recommendations must be explainable"
        assert len({c["teacher_id"] for c in slot["candidates"]}) == len(slot["candidates"])
        # No candidate may be busy at the affected period.
        busy = _busy_periods(client, headers, slot)
        for candidate in slot["candidates"]:
            assert candidate["teacher_id"] not in busy


def _busy_periods(client: TestClient, headers: dict, slot: dict) -> set[int]:
    res = client.get("/api/v1/school/timetable", headers=headers)
    return {
        s["teacher_id"]
        for s in res.json()["slots"]
        if s["day_of_week"] == dt.date.today().weekday() and s["period_number"] == slot["period_number"]
    }


def test_duplicate_absence_rejected(client):
    headers = _school_user_headers(client)
    today = dt.date.today()
    with SessionLocal() as db:
        slots = db.query(TimetableSlot).filter(
            TimetableSlot.school_id == 3, TimetableSlot.day_of_week == today.weekday()
        )
        already_absent = {
            a.teacher_id for a in db.query(TeacherAbsence).filter_by(school_id=3, absence_date=today)
        }
        teacher_id = next(s.teacher_id for s in slots if s.teacher_id not in already_absent)
    first = client.post(
        "/api/v1/school/absences",
        headers=headers,
        json={"teacher_id": teacher_id, "absence_date": today.isoformat()},
    )
    assert first.status_code == 201, first.text
    res = client.post(
        "/api/v1/school/absences",
        headers=headers,
        json={"teacher_id": teacher_id, "absence_date": today.isoformat()},
    )
    assert res.status_code == 409


def test_confirm_substitution_marks_slot_covered(client):
    headers = _school_user_headers(client)
    today = dt.date.today()
    with SessionLocal() as db:
        slots = (
            db.query(TimetableSlot)
            .filter(TimetableSlot.school_id == 3, TimetableSlot.day_of_week == today.weekday())
            .all()
        )
        already_absent = {
            a.teacher_id for a in db.query(TeacherAbsence).filter_by(school_id=3, absence_date=today)
        }
        other_teacher = next(s.teacher_id for s in slots if s.teacher_id not in already_absent)

    res = client.post(
        "/api/v1/school/absences",
        headers=headers,
        json={"teacher_id": other_teacher, "absence_date": today.isoformat(), "reason": "Panel test"},
    )
    assert res.status_code == 201, res.text
    panel = res.json()["panel"]
    slot = panel["slots"][0]
    candidate = slot["candidates"][0]

    confirm = client.post(
        "/api/v1/school/substitutions",
        headers=headers,
        json={
            "absence_id": panel["absence_id"],
            "period_number": slot["period_number"],
            "class_id": slot["class_id"],
            "substitute_teacher_id": candidate["teacher_id"],
        },
    )
    assert confirm.status_code == 201, confirm.text
    panel_after = confirm.json()["panel"]
    target = next(
        s
        for s in panel_after["slots"]
        if s["period_number"] == slot["period_number"] and s["class_id"] == slot["class_id"]
    )
    assert target["covered"] is True
    assert panel_after["slots_uncovered"] == panel_after["slots_total"] - 1


def test_auto_assign_covers_all_slots_and_flags_absence(client):
    headers = _school_user_headers(client)
    today = dt.date.today()
    with SessionLocal() as db:
        # Pick a teacher with several slots today and no absence yet.
        slots = (
            db.query(TimetableSlot)
            .filter(TimetableSlot.school_id == 3, TimetableSlot.day_of_week == today.weekday())
            .all()
        )
        counts: dict[int, int] = {}
        for s in slots:
            counts[s.teacher_id] = counts.get(s.teacher_id, 0) + 1
        existing = {a.teacher_id for a in db.query(TeacherAbsence).filter_by(school_id=3, absence_date=today)}
        teacher_id = next(
            tid for tid, n in sorted(counts.items(), key=lambda kv: -kv[1]) if tid not in existing
        )

    res = client.post(
        "/api/v1/school/absences",
        headers=headers,
        json={"teacher_id": teacher_id, "absence_date": today.isoformat(), "reason": "Auto-cover drill"},
    )
    assert res.status_code == 201
    absence_id = res.json()["panel"]["absence_id"]

    auto = client.post(
        f"/api/v1/school/absences/{absence_id}/auto-assign", headers=headers
    )
    assert auto.status_code == 200, auto.text
    panel = auto.json()["panel"]
    assert panel["slots_uncovered"] == 0
    assert auto.json()["assigned"] == panel["slots_total"]
    assert res.json()["absence"]["status"] in ("logged", "covered")

    refreshed = client.get(
        f"/api/v1/school/absences/{absence_id}/recommendations", headers=headers
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["slots_uncovered"] == 0


def test_state_role_is_firewalled_from_tenant_absences(client, state_token):
    res = client.get(
        "/api/v1/school/absences", headers={"Authorization": f"Bearer {state_token}"}
    )
    assert res.status_code == 403
    assert "FIREWALL" in res.json()["detail"]


def test_cancel_absence(client):
    headers = _school_user_headers(client)
    today = dt.date.today()
    with SessionLocal() as db:
        slot = (
            db.query(TimetableSlot)
            .filter(TimetableSlot.school_id == 3, TimetableSlot.day_of_week == today.weekday())
            .first()
        )
        teacher_id = slot.teacher_id
    res = client.post(
        "/api/v1/school/absences",
        headers=headers,
        json={"teacher_id": teacher_id, "absence_date": (today + dt.timedelta(days=1)).isoformat()},
    )
    assert res.status_code == 201
    absence_id = res.json()["panel"]["absence_id"]
    cancel = client.delete(f"/api/v1/school/absences/{absence_id}", headers=headers)
    assert cancel.status_code == 200
    assert cancel.json()["absence"]["status"] == "cancelled"


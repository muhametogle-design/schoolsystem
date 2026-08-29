"""Phase 2 — the 3:00 PM Red Alarm compliance worker."""

from __future__ import annotations

import datetime as dt

from app.core.db import SessionLocal
from app.models import CommunicationLog, DailySubmissionLog, PrivateSchool
from app.services.compliance import process_daily_attendance_deadlines


def _school_id(name: str) -> int:
    with SessionLocal() as db:
        return db.query(PrivateSchool).filter_by(school_name=name).one().id


def test_audit_raises_red_alarm_for_non_submitters(client, auth_headers):
    res = client.post("/api/state/audit/run", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    alarmed = {a["school_name"] for a in body["alarms"]}
    assert "Horizon Preparatory School" in alarmed      # never submitted today
    assert "Greenfield Academy" not in alarmed           # submitted 09:42
    assert "Crescent International School" not in alarmed  # submitted 11:17
    assert "Iftin Community School" not in alarmed       # Probation => not active target


def test_alarm_persists_log_and_communication(client):
    horizon = _school_id("Horizon Preparatory School")
    with SessionLocal() as db:
        log = (
            db.query(DailySubmissionLog)
            .filter_by(school_id=horizon, log_date=dt.date.today())
            .one()
        )
        assert log.alarm_triggered is True
        assert log.attendance_submitted is False
        assert log.alarm_raised_at is not None

        msg = (
            db.query(CommunicationLog)
            .filter_by(school_id=horizon, message_type="Red_Alarm")
            .order_by(CommunicationLog.id.desc())
            .first()
        )
        assert msg is not None
        assert "CRITICAL COMPLIANCE BREACH" in msg.message_content
        assert msg.recipient_phone == "STATE_DASHBOARD_ALARM_PIPELINE"


def test_compliance_map_reflects_alarm(client, auth_headers):
    body = client.get("/api/state/compliance-map", headers=auth_headers).json()
    horizon_row = next(r for r in body["schools"] if r["school_name"] == "Horizon Preparatory School")
    assert horizon_row["is_red_alarm_active"] is True
    assert "RED ALARM" in horizon_row["state_compliance_status"]
    assert body["summary"]["red_alarms"] >= 1


def test_late_submission_prevents_future_alarms(client, horizon_manager_headers, auth_headers):
    """Once the school submits (even after the deadline), the next audit stays quiet."""
    # Horizon records + submits today's roster through the ERP API
    students = client.get(
        "/api/school/students", headers=horizon_manager_headers
    ).json()["students"]
    assert students, "Horizon has no students"
    entries = [{"student_id": s["id"], "status": "Present"} for s in students[:5]]
    class_id = None
    # find one class and submit a valid roster for it
    classes = client.get("/api/school/classes", headers=horizon_manager_headers).json()["classes"]
    for c in classes:
        roster = client.get(
            f"/api/school/students?class_id={c['id']}", headers=horizon_manager_headers
        ).json()["students"]
        if roster:
            class_id = c["id"]
            entries = [{"student_id": s["id"], "status": "Present"} for s in roster]
            break

    today = dt.date.today().isoformat()
    assert client.post(
        "/api/school/attendance",
        headers=horizon_manager_headers,
        json={"date": today, "class_id": class_id, "entries": entries},
    ).status_code == 200

    res = client.post(
        "/api/school/attendance/submit",
        headers=horizon_manager_headers,
        json={"date": today},
    )
    assert res.status_code == 200
    assert res.json()["attendance_submitted"] is True

    # Re-run the audit: Horizon must NOT be re-alarmed
    body = client.post("/api/state/audit/run", headers=auth_headers).json()
    alarmed = {a["school_name"] for a in body["alarms"]}
    assert "Horizon Preparatory School" not in alarmed

    # The historical alarm flag is preserved for the audit trail
    horizon = _school_id("Horizon Preparatory School")
    with SessionLocal() as db:
        log = db.query(DailySubmissionLog).filter_by(school_id=horizon, log_date=dt.date.today()).one()
        assert log.attendance_submitted is True
        assert log.alarm_triggered is True  # breach history is immutable

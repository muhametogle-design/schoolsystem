"""IMPLEMENTATION PHASE 2 — THE 3:00 PM RED ALARM COMPLIANCE WORKER.

`process_daily_attendance_deadlines` executes daily via the worker scheduler
at exactly 15:00 (3:00 PM) — three hours past the mandatory 12:00 PM state
attendance deadline. For every active private school that failed to submit
its daily roster it:

  1. UPSERTs daily_submission_logs with alarm_triggered = TRUE,
  2. queues a critical Red_Alarm record in the communication gateway,
  3. streams the live update instantly to all state_inspector client browser
     connections over WebSockets.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.db import IS_SQLITE
from app.core.ws import emit_live_websocket_alarm_event
from app.models import CommunicationLog, DailySubmissionLog, PrivateSchool


def _upsert_insert():
    return sqlite_insert(DailySubmissionLog) if IS_SQLITE else pg_insert(DailySubmissionLog)


def process_daily_attendance_deadlines(
    database_session: Session,
    *,
    broadcaster=emit_live_websocket_alarm_event,
) -> list[dict]:
    """Audits which active private schools missed their mandatory 12:00 PM entry.

    Returns a summary of every red alarm raised during this audit run.
    """
    today_date = dt.date.today()
    raised: list[dict] = []

    # Extract active target systems
    active_schools = database_session.execute(
        select(PrivateSchool.id, PrivateSchool.school_name).where(
            PrivateSchool.accreditation_status == "Active"
        )
    ).all()

    for school in active_schools:
        log = database_session.execute(
            select(DailySubmissionLog).where(
                DailySubmissionLog.school_id == school.id,
                DailySubmissionLog.log_date == today_date,
            )
        ).scalar_one_or_none()

        # If no validation record or submission exists, trigger the visual Red Alarm
        if not log or not log.attendance_submitted:
            stmt = (
                _upsert_insert()
                .values(
                    school_id=school.id,
                    log_date=today_date,
                    attendance_submitted=False,
                    alarm_triggered=True,
                    alarm_raised_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
                )
                .on_conflict_do_update(
                    index_elements=["school_id", "log_date"],
                    set_={"alarm_triggered": True, "alarm_raised_at": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)},
                )
            )
            database_session.execute(stmt)

            # Queue standard outbound system alerts
            alert_text = (
                f"CRITICAL COMPLIANCE BREACH: {school.school_name} has triggered a RED ALARM "
                "for failing to submit attendance logs by the 12:00 PM state deadline."
            )
            database_session.add(
                CommunicationLog(
                    school_id=school.id,
                    recipient_phone="STATE_DASHBOARD_ALARM_PIPELINE",
                    message_type="Red_Alarm",
                    message_content=alert_text,
                    delivery_status="Pending",
                )
            )

            # AI Agent Note: Stream this live update instantly to all
            # state_inspector active client browser connections using
            # WebSockets / Socket.io events.
            broadcaster(school_id=school.id, message=alert_text, school_name=school.school_name)

            raised.append(
                {
                    "school_id": school.id,
                    "school_name": school.school_name,
                    "alarm_triggered": True,
                    "message": alert_text,
                }
            )

    database_session.commit()
    return raised


def submit_daily_attendance_roster(database_session: Session, *, school_id: int, user_id: int | None, log_date: dt.date | None = None) -> DailySubmissionLog:
    """Registers the school's mandatory daily roster submission.

    Late (post-noon) submissions are still accepted — the 15:00 worker only
    escalates schools with NO submission at all — but the timestamp preserves
    the full audit trail.
    """
    log_date = log_date or dt.date.today()
    submitted_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    stmt = (
        _upsert_insert()
        .values(
            school_id=school_id,
            log_date=log_date,
            attendance_submitted=True,
            attendance_submitted_at=submitted_at,
        )
        .on_conflict_do_update(
            index_elements=["school_id", "log_date"],
            set_={"attendance_submitted": True, "attendance_submitted_at": submitted_at},
        )
    )
    database_session.execute(stmt)
    database_session.commit()

    log = database_session.execute(
        select(DailySubmissionLog).where(
            DailySubmissionLog.school_id == school_id, DailySubmissionLog.log_date == log_date
        )
    ).scalar_one()
    return log

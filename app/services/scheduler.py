"""In-process worker cron: fires the Red Alarm audit daily at exactly 15:00."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.ws import manager

logger = logging.getLogger("worker.scheduler")


def _seconds_until(next_hhmm: str, tz: ZoneInfo) -> float:
    now = dt.datetime.now(tz)
    hh, mm = (int(part) for part in next_hhmm.split(":"))
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return (target - now).total_seconds() + 1.0


async def compliance_scheduler_loop() -> None:
    """Sleeps until the next 15:00 (platform timezone), runs the Phase 2
    worker in a thread with its own DB session, then reschedules."""
    from app.services.compliance import process_daily_attendance_deadlines
    from app.core.db import SessionLocal, set_rls_context

    tz = ZoneInfo(settings.platform_timezone)
    logger.info(
        "Compliance scheduler armed: daily audit at %s %s "
        "(attendance deadline %s)",
        settings.alarm_audit_time,
        tz,
        settings.attendance_deadline,
    )
    while True:
        try:
            wait = _seconds_until(settings.alarm_audit_time, tz)
            await asyncio.sleep(wait)

            def _run():
                with SessionLocal() as session:
                    # Trusted platform job: it audits every tenant after the
                    # deadline and therefore runs under the State Admin scope.
                    set_rls_context(session, school_id=None, role="state_admin")
                    return process_daily_attendance_deadlines(session)

            alarms = await asyncio.to_thread(_run)
            await manager.broadcast(
                "audit_completed",
                {
                    "ran_at": dt.datetime.now(tz).isoformat(),
                    "alarm_count": len(alarms),
                    "alarms": alarms,
                },
            )
            logger.info("15:00 audit executed: %d red alarm(s) raised", len(alarms))
        except asyncio.CancelledError:
            logger.info("Compliance scheduler cancelled.")
            raise
        except Exception:  # pragma: no cover - keep the worker alive
            logger.exception("Compliance audit run failed; retrying in 60s")
            await asyncio.sleep(60)


async def backup_scheduler_loop() -> None:
    """Module 4 — automated encrypted export at midnight (platform timezone).

    Runs the full pipeline (SQLite snapshot or JSON delta, AES-256-GCM seal,
    SHA-256/MD5 digests, audit trail) in a thread with its own DB session,
    then reschedules for the next midnight.
    """
    from app.core.db import SessionLocal

    tz = ZoneInfo(settings.platform_timezone)
    logger.info(
        "Backup scheduler armed: daily encrypted export at %s %s (retention %dd)",
        settings.backup_time,
        tz,
        settings.backup_retention_days,
    )
    while True:
        try:
            wait = _seconds_until(settings.backup_time, tz)
            await asyncio.sleep(wait)

            def _run():
                from app.services.backup import run_scheduled_backup

                return run_scheduled_backup()

            record = await asyncio.to_thread(_run)
            await manager.broadcast(
                "backup_completed",
                {
                    "backup_id": record.id,
                    "kind": record.kind,
                    "status": record.status,
                    "size_bytes": record.size_bytes,
                    "sha256": record.sha256,
                    "triggered_by": "scheduled",
                },
            )
            logger.info("Midnight backup executed: %s (%s)", record.filename, record.status)
        except asyncio.CancelledError:
            logger.info("Backup scheduler cancelled.")
            raise
        except Exception:  # pragma: no cover - keep the worker alive
            logger.exception("Midnight backup failed; retrying in 120s")
            await asyncio.sleep(120)

"""Private School Management & State Compliance Monitoring System — API entrypoint.

Boot sequence:
  1. Create tables (portable fallback; PostgreSQL deployments should run sql/).
  2. Auto-seed the demo tier when the database comes up empty.
  3. Arm the in-process 15:00 Red Alarm worker cron.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, billing, health, school, state, ws
from app.core.config import settings
from app.core.db import SessionLocal, init_db, IS_SQLITE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

_scheduler_task: asyncio.Task | None = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler_task

    init_db()

    if settings.auto_seed_demo:
        from scripts.seed_data import seed_if_empty

        with SessionLocal() as session:
            seed_if_empty(session)

    if settings.enable_scheduler:
        from app.services.scheduler import compliance_scheduler_loop

        _scheduler_task = asyncio.create_task(compliance_scheduler_loop())

    logger.info("Platform up — attendance deadline %s, red alarm audit at %s %s",
                settings.attendance_deadline, settings.alarm_audit_time, settings.platform_timezone)
    yield

    if _scheduler_task:
        _scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _scheduler_task


app = FastAPI(
    title="Private School Management & State Compliance Monitoring System",
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "Multi-tenant SaaS for state-supervised private schools (Class 1-12). "
        "Tenant ERP + State read-only compliance visibility, the 12:00 PM "
        "attendance deadline, the 15:00 RED ALARM engine with live WebSocket "
        "alerts, the Exam Data Release Valve, and a hard financial firewall."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(state.router)
app.include_router(school.router)
app.include_router(billing.router)
app.include_router(ws.router)

if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")

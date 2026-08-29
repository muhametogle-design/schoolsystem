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
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    analytics,
    auth,
    billing,
    health,
    school,
    state,
    state_oversight,
    students,
    ws,
)
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

    # Bind the main event loop so worker threads can broadcast over /ws.
    from app.core.ws import manager as _manager

    _manager.bind_loop(asyncio.get_running_loop())

    if settings.auto_seed_demo:
        from scripts.seed_data import seed_if_empty

        with SessionLocal() as session:
            seed_if_empty(session)

    if settings.enable_scheduler:
        from app.services.scheduler import compliance_scheduler_loop

        _scheduler_task = asyncio.create_task(compliance_scheduler_loop())

    if settings.app_env == "production" and settings.jwt_secret_key.startswith("dev-only"):
        logger.warning("⚠️  JWT_SECRET_KEY is still the development default — rotate it before serving traffic.")

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
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def production_hardening(request: Request, call_next):
    """Security headers + structured request logging + leak-free 500s.

    Note: no X-Frame-Options / CSP frame-ancestors restrictions are set so the
    platform can be embedded in approved dashboard frames; tighten them to your
    deployment's frame origin in production (see DEPLOYMENT.md).
    """
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.path.startswith("/api"):
        logger.info(
            '%s %s -> %d (%.1f ms)',
            request.method, request.url.path, response.status_code, duration_ms,
        )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak stack traces to clients; full detail stays in server logs."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(state.router)
app.include_router(school.router)
# NE-EMIS: student profiles, school analytics and state institutional oversight.
# Registered after `school` so the class-grouped and NE-SID routes win.
app.include_router(students.router)
app.include_router(analytics.router)
app.include_router(state_oversight.router)
app.include_router(billing.router)
app.include_router(ws.router)


# ---------------- STEP 4: Interface portal routes ----------------
# The React workspace (web/) is the primary interface when it has been built.
# The original vanilla SPA under frontend/ stays available at /admin/* so an
# unbuilt checkout still has a working dashboard.
_REACT_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"
HAS_REACT_BUILD = (_REACT_DIR / "index.html").exists()

if HAS_REACT_BUILD:
    app.mount(
        "/assets",
        StaticFiles(directory=str(_REACT_DIR / "assets")),
        name="react-assets",
    )

    @app.get("/favicon.svg", include_in_schema=False)
    async def react_favicon() -> FileResponse:
        icon = _REACT_DIR / "favicon.svg"
        return FileResponse(icon if icon.exists() else _FRONTEND_DIR / "favicon.svg")

    # Client-side routes must all resolve to the shell so a page refresh (or a
    # bookmarked /students/NE-SID-… deep link) still boots the SPA.
    @app.get("/", include_in_schema=False)
    @app.get("/school", include_in_schema=False)
    @app.get("/school/{full_path:path}", include_in_schema=False)
    @app.get("/state", include_in_schema=False)
    @app.get("/state/{full_path:path}", include_in_schema=False)
    async def react_shell() -> FileResponse:
        return FileResponse(_REACT_DIR / "index.html")


@app.get("/admin/state", include_in_schema=False)
@app.get("/admin/school", include_in_schema=False)
@app.get("/admin", include_in_schema=False)
async def interface_portal() -> FileResponse:
    return FileResponse(_FRONTEND_DIR / "index.html")


if not HAS_REACT_BUILD and _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")

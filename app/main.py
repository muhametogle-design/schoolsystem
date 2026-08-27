"""NE-EMIS API entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    aggregation,
    auth,
    demo,
    health,
    ingestion,
    locking,
    state,
    students,
    teachers,
)
from app.core.config import settings

app = FastAPI(
    title=f"{settings.app_name} API",
    version="1.0.0",
    description=(
        "Multi-tenant cloud-based Education Management Information System. "
        "Campus-isolated RLS writes + centralised state aggregation through a "
        "four-phase ingestion pipeline."
    ),
    openapi_url="/openapi.json",
    docs_url="/docs",
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
app.include_router(students.router)
app.include_router(teachers.router)
app.include_router(ingestion.router)
app.include_router(locking.router)
app.include_router(aggregation.router)
app.include_router(state.router)
app.include_router(demo.router)

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


# Serve the demo dashboard; explicit API routes above take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

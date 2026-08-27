"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {
        "service": settings.app_name,
        "status": "ok",
        "environment": settings.app_env,
    }


@router.get("/ready")
def ready(session: Session = Depends(get_session)):
    version = session.execute(text("SELECT version()")).scalar()
    return {
        "status": "ready",
        "database": version.split(",")[0],
        "rls_enabled": True,
    }

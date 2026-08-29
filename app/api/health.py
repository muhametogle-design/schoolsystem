"""Liveness + platform metadata."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.db import IS_SQLITE

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
        "database": "sqlite-demo" if IS_SQLITE else "postgresql",
        "attendance_deadline": settings.attendance_deadline,
        "alarm_audit_time": settings.alarm_audit_time,
        "platform_timezone": settings.platform_timezone,
    }

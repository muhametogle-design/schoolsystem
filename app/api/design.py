"""Dynamic design system configuration & publishing controls (Refinements 7-8).

The *live* design configuration — global accent colour, typography preset and
dashboard block visibility — is stored on the tenant record as JSON. Everyone
in the school reads it; only School Managers may publish a new one.

Draft flow (client-side): a manager experiments in the Design & Layout drawer,
presses **Save Progress** to persist the draft locally in their own browser,
and presses **Push Live** when ready — which is exactly the guarded ``PUT``
below. Every publish is versioned with ``published_at``/``published_by`` and
audited, so the production sync is traceable.
"""

from __future__ import annotations

import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import _audit, require_school
from app.core.db import get_db
from app.models import PrivateSchool, User
from app.schemas import ALLOWED_ACCENTS, ALLOWED_FONTS, DesignConfigPayload

router = APIRouter(prefix="/api/v1/school/design-config", tags=["design-system"])

any_school_user = require_school()
manager_only = require_school("school_manager")

#: What every user receives before the manager has ever pushed a theme live.
DEFAULT_CONFIG = {
    "accent": ALLOWED_ACCENTS[0],
    "font": "sans",
    "blocks": {
        "profileCard": True,
        "academicOverview": True,
        "attendanceSummary": True,
        "biometricsBadge": True,
    },
}


def _school_or_404(db: Session, school_id: int | None) -> PrivateSchool:
    school = db.get(PrivateSchool, school_id)
    if not school:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "School not found")
    return school


def _read_config(school: PrivateSchool) -> dict:
    """Merge the stored JSON over defaults so legacy tenants stay valid."""
    if not school.design_config:
        return {**DEFAULT_CONFIG, "published_at": None, "published_by": None}
    try:
        stored = json.loads(school.design_config)
    except (TypeError, ValueError):
        stored = {}
    return {
        "accent": stored.get("accent") if stored.get("accent") in ALLOWED_ACCENTS else DEFAULT_CONFIG["accent"],
        "font": stored.get("font") if stored.get("font") in ALLOWED_FONTS else DEFAULT_CONFIG["font"],
        "blocks": {**DEFAULT_CONFIG["blocks"], **(stored.get("blocks") or {})},
        "published_at": stored.get("published_at"),
        "published_by": stored.get("published_by"),
    }


@router.get("")
def get_design_config(user: User = Depends(any_school_user), db: Session = Depends(get_db)):
    """Live theme configuration — readable by every authenticated school user."""
    school = _school_or_404(db, user.school_id)
    return {"school": school.school_name, "config": _read_config(school)}


@router.put("")
def push_design_config(
    payload: DesignConfigPayload,
    request: Request,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """Push Live — sync the design system to production (managers only)."""
    if payload.accent.lower() not in ALLOWED_ACCENTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Accent {payload.accent} is not in the approved palette: {', '.join(ALLOWED_ACCENTS)}",
        )
    if payload.font not in ALLOWED_FONTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Font preset must be one of: {', '.join(ALLOWED_FONTS)}",
        )
    school = _school_or_404(db, user.school_id)
    config = {
        "accent": payload.accent.lower(),
        "font": payload.font,
        "blocks": payload.sanitized_blocks(),
        "published_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "published_by": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
    }
    school.design_config = json.dumps(config)
    db.commit()
    _audit(db, user, request, "ALLOWED", "Design system pushed live to production configuration")
    return {
        "message": "Design system pushed live — accent, typography and layout blocks are now in production.",
        "config": _read_config(school),
    }

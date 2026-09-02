"""Pydantic UI configuration contract for the Arena OS platform.

This module owns the pure *configuration* schema used to drive a school
workspace's user-interface chrome (theme colours, typeface, dark mode and
branding). Unlike the ORM models in this package it is not a database table —
``SchoolUiConfig`` is a stateless value object exported through ``app.models``
so the rest of the codebase can import it via ``from app.models import
SchoolUiConfig`` without reaching into an internal module.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SchoolUiConfig(BaseModel):
    """User-interface theming configuration for a school workspace.

    Defaults mirror the platform's default palette, so a freshly provisioned
    tenant renders immediately without needing a persisted config row.
    """

    primary_color: str = "#2563eb"
    font_family: str = "sans-serif"
    is_dark: bool = True
    logo_url: Optional[str] = None

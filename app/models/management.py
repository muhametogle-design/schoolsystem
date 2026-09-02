"""Management tier — tenant-level UI / branding configuration.

Unlike the other modules in this package, ``SchoolUiConfig`` is a Pydantic
model rather than a SQLAlchemy table. It describes the per-school interface
theme (brand colour, typography, dark/light mode, logo) consumed by the Arena
OS dashboards, and provides the validated default theme every tenant starts
from before a manager customises it.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SchoolUiConfig(BaseModel):
    """Per-tenant interface theme for the Arena OS dashboards.

    Defaults deliberately match the shipped frontend theme so a school with no
    stored customisation renders identically to a fresh installation.
    """

    primary_color: str = "#2563eb"
    font_family: str = "sans-serif"
    is_dark: bool = True
    logo_url: Optional[str] = None

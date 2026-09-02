"""Platform upgrade regression suite.

Verifies the freshly exported ``SchoolUiConfig`` Pydantic model (part of the
Arena OS UI configuration management work) and confirms the FastAPI entrypoint
still boots without import errors.

These tests are deliberately unit/integration-light: they exercise the model
contract and the import graph without requiring a live database, so the suite
is fast and deterministic.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.main import app as fastapi_app
from app.models import SchoolUiConfig


def test_school_ui_config_clean_import_from_app_models():
    """``SchoolUiConfig`` is exported from the public ``app.models`` package."""
    assert SchoolUiConfig is not None
    assert SchoolUiConfig.__name__ == "SchoolUiConfig"
    assert issubclass(SchoolUiConfig, BaseModel)


def test_default_schema_attribute_validation():
    """The documented defaults are applied and typed correctly."""
    config = SchoolUiConfig()
    assert config.is_dark is True
    assert config.primary_color == "#2563eb"
    assert config.font_family == "sans-serif"
    assert config.logo_url is None

    # The defaults must be genuine primitives of the declared types.
    assert isinstance(config.is_dark, bool)
    assert isinstance(config.primary_color, str)
    assert isinstance(config.font_family, str)


def test_model_instantiation_with_custom_overrides():
    """Every field can be overridden at construction time."""
    config = SchoolUiConfig(
        primary_color="#0f172a",
        font_family="Inter",
        is_dark=False,
        logo_url="https://cdn.example.com/logo.png",
    )
    assert config.primary_color == "#0f172a"
    assert config.font_family == "Inter"
    assert config.is_dark is False
    assert config.logo_url == "https://cdn.example.com/logo.png"


def test_model_dump_round_trip():
    """``model_dump`` exposes the schema's canonical default shape."""
    assert SchoolUiConfig().model_dump() == {
        "primary_color": "#2563eb",
        "font_family": "sans-serif",
        "is_dark": True,
        "logo_url": None,
    }


def test_schema_rejects_invalid_field_types():
    """Pydantic refuses values that cannot be coerced to the declared types."""
    with pytest.raises(ValidationError):
        SchoolUiConfig(is_dark="definitely-not-a-boolean")


def test_app_main_initializes_without_import_errors():
    """``app.main:app`` is importable and exposes a valid FastAPI instance."""
    assert fastapi_app is not None
    assert fastapi_app.title

"""Platform upgrade regression suite — Arena OS UI configuration model.

Covers:
  * the ``SchoolUiConfig`` export from the ``app.models`` registry,
  * the shipped default theme values,
  * instantiation with custom overrides (and Pydantic validation),
  * ``app.main:app`` importing and booting cleanly through its lifespan.

The environment pins in ``tests/conftest.py`` (SQLite demo tier, no auto-seed,
no scheduler) apply before any ``app`` import below.
"""

from __future__ import annotations

import importlib

import pytest
from pydantic import BaseModel, ValidationError


# ---------------------------------------------------------------------------
# 1. Clean import from the model registry
# ---------------------------------------------------------------------------
def test_school_ui_config_imports_from_models_package():
    from app.models import SchoolUiConfig

    assert SchoolUiConfig is not None
    assert issubclass(SchoolUiConfig, BaseModel)


def test_school_ui_config_is_declared_in_models_all():
    import app.models as models

    assert "SchoolUiConfig" in models.__all__
    # The public name must resolve to the object defined in the source module.
    from app.models.management import SchoolUiConfig as source_cls

    assert getattr(models, "SchoolUiConfig") is source_cls


def test_star_import_exposes_school_ui_config():
    """``from app.models import *`` must carry the symbol (drives ``__all__``)."""
    namespace: dict[str, object] = {}
    exec("from app.models import *", namespace)  # noqa: S102 - controlled test input
    assert "SchoolUiConfig" in namespace


def test_management_module_is_importable_on_its_own():
    module = importlib.import_module("app.models.management")
    assert hasattr(module, "SchoolUiConfig")


# ---------------------------------------------------------------------------
# 2. Default schema attributes
# ---------------------------------------------------------------------------
def test_default_theme_values():
    from app.models import SchoolUiConfig

    config = SchoolUiConfig()
    assert config.is_dark is True
    assert config.primary_color == "#2563eb"
    assert config.font_family == "sans-serif"
    assert config.logo_url is None


def test_schema_declares_exactly_the_expected_fields():
    from app.models import SchoolUiConfig

    assert set(SchoolUiConfig.model_fields) == {
        "primary_color",
        "font_family",
        "is_dark",
        "logo_url",
    }
    # Every field carries a default, so a bare ``SchoolUiConfig()`` is valid.
    for name, field in SchoolUiConfig.model_fields.items():
        assert not field.is_required(), f"{name} should have a default value"


def test_default_serialization_round_trip():
    from app.models import SchoolUiConfig

    dumped = SchoolUiConfig().model_dump()
    assert dumped == {
        "primary_color": "#2563eb",
        "font_family": "sans-serif",
        "is_dark": True,
        "logo_url": None,
    }
    assert SchoolUiConfig.model_validate(dumped) == SchoolUiConfig()


# ---------------------------------------------------------------------------
# 3. Instantiation with custom overrides
# ---------------------------------------------------------------------------
def test_custom_overrides_are_applied():
    from app.models import SchoolUiConfig

    config = SchoolUiConfig(
        primary_color="#0f766e",
        font_family="Inter, system-ui",
        is_dark=False,
        logo_url="https://cdn.example.edu/alqalam/logo.svg",
    )
    assert config.primary_color == "#0f766e"
    assert config.font_family == "Inter, system-ui"
    assert config.is_dark is False
    assert config.logo_url == "https://cdn.example.edu/alqalam/logo.svg"


def test_partial_override_keeps_remaining_defaults():
    from app.models import SchoolUiConfig

    config = SchoolUiConfig(is_dark=False)
    assert config.is_dark is False
    assert config.primary_color == "#2563eb"
    assert config.font_family == "sans-serif"
    assert config.logo_url is None


def test_overrides_validate_from_untrusted_payload():
    """Payloads arriving as JSON-ish dicts must be coerced and validated."""
    from app.models import SchoolUiConfig

    config = SchoolUiConfig.model_validate(
        {"primary_color": "#111827", "is_dark": "false", "logo_url": None}
    )
    assert config.primary_color == "#111827"
    assert config.is_dark is False  # lax bool coercion from a string
    assert config.logo_url is None


@pytest.mark.parametrize(
    "payload",
    [
        {"is_dark": "not-a-bool"},
        {"primary_color": ["#2563eb"]},
        {"font_family": {"family": "serif"}},
        {"logo_url": 12345},
    ],
)
def test_invalid_overrides_are_rejected(payload):
    from app.models import SchoolUiConfig

    with pytest.raises(ValidationError):
        SchoolUiConfig(**payload)


def test_model_copy_with_update_produces_independent_theme():
    from app.models import SchoolUiConfig

    base = SchoolUiConfig()
    branded = base.model_copy(update={"primary_color": "#dc2626"})
    assert branded.primary_color == "#dc2626"
    assert base.primary_color == "#2563eb"
    assert branded != base


# ---------------------------------------------------------------------------
# 4. app.main:app initialises without import errors
# ---------------------------------------------------------------------------
def test_app_main_imports_without_errors():
    module = importlib.import_module("app.main")
    from fastapi import FastAPI

    assert isinstance(module.app, FastAPI)
    assert module.app.title


def test_app_registers_core_api_routes():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/health" in paths
    assert "/api/auth/login" in paths


def test_app_boots_through_lifespan_and_serves_health(client):
    """The shared session client runs the lifespan (init_db) — a real boot."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

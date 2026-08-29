"""Test bootstrap.

Environment is pinned BEFORE any `app` import so every module sees the same
SQLite-backed demo tier (the PostgreSQL DDL is exercised via docker-compose).
"""

from __future__ import annotations

import os
import pathlib

_TEST_DB = pathlib.Path(__file__).resolve().parent / "_test_schoolsystem.db"

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["AUTO_SEED_DEMO"] = "false"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import SessionLocal, init_db  # noqa: E402


@pytest.fixture(scope="session")
def client():
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    from app.main import app

    with TestClient(app) as c:  # lifespan: init_db() creates all tables
        from scripts.seed_data import seed

        with SessionLocal() as session:
            seed(session)
        yield c


def _login(client: TestClient, email: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture(scope="session")
def state_token(client):
    return _login(client, "inspector@education.gov", "State@2026")


@pytest.fixture(scope="session")
def greenfield_manager_token(client):
    return _login(client, "manager@greenfield.edu", "School@2026")


@pytest.fixture(scope="session")
def greenfield_teacher_token(client):
    return _login(client, "teacher@greenfield.edu", "Teach@2026")


@pytest.fixture(scope="session")
def horizon_manager_token(client):
    return _login(client, "manager@horizon.edu", "School@2026")


@pytest.fixture(scope="session")
def auth_headers(state_token):
    return {"Authorization": f"Bearer {state_token}"}


@pytest.fixture(scope="session")
def greenfield_manager_headers(greenfield_manager_token):
    return {"Authorization": f"Bearer {greenfield_manager_token}"}


@pytest.fixture(scope="session")
def greenfield_teacher_headers(greenfield_teacher_token):
    return {"Authorization": f"Bearer {greenfield_teacher_token}"}


@pytest.fixture(scope="session")
def horizon_manager_headers(horizon_manager_token):
    return {"Authorization": f"Bearer {horizon_manager_token}"}

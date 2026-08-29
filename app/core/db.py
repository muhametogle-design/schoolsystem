"""Database engine + session management (PostgreSQL production / SQLite demo)."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

IS_SQLITE = settings.database_url.startswith("sqlite")

_engine_kwargs: dict = {"pool_pre_ping": True}
if IS_SQLITE:
    _db_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(_db_dir, exist_ok=True)
    _engine_kwargs.update({"connect_args": {"check_same_thread": False}})

engine = create_engine(settings.database_url, **_engine_kwargs)

# Enforce foreign keys + WAL on the SQLite demo tier (Postgres needs nothing here).
if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - driver glue
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables from the ORM metadata.

    On PostgreSQL, prefer running sql/001_schema.sql + 002_security_firewall.sql
    + 003_analytics_views.sql as the authoritative Phase 1 DDL; metadata.create_all
    is the portable fallback used by the demo tier and tests.
    """
    from app.models import Base  # noqa: F401  (imports every model)

    Base.metadata.create_all(bind=engine)

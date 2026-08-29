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


#: Columns introduced after the initial release. `create_all` only creates
#: missing *tables*, never missing columns — without this, an existing demo
#: database would never pick up the NE-SID / fee-status / staff-profile fields.
COLUMN_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("users", "staff_identifier", "VARCHAR(30)"),
    ("users", "phone", "VARCHAR(50)"),
    ("users", "qualifications", "TEXT"),
    ("users", "designation", "VARCHAR(100)"),
    ("users", "is_active", "BOOLEAN DEFAULT 1"),
    ("students", "physical_address", "TEXT"),
    ("students", "fee_status", "VARCHAR(20) DEFAULT 'NOT_PAID'"),
)


def _existing_columns(connection, table: str) -> set[str]:
    """Column names currently present on `table` (SQLite + PostgreSQL)."""
    if IS_SQLITE:
        rows = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}
    rows = connection.exec_driver_sql(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table,),
    ).fetchall()
    return {row[0] for row in rows}


def _table_exists(connection, table: str) -> bool:
    if IS_SQLITE:
        row = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
    else:
        row = connection.exec_driver_sql(
            "SELECT tablename FROM pg_tables WHERE tablename = %s", (table,)
        ).fetchone()
    return row is not None


def apply_column_migrations() -> None:
    """Idempotently add any missing columns to pre-existing tables."""
    with engine.begin() as connection:
        for table, column, ddl in COLUMN_MIGRATIONS:
            if not _table_exists(connection, table):
                continue
            if column in _existing_columns(connection, table):
                continue
            connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    """Create tables from the ORM metadata, then add any missing columns.

    On PostgreSQL, prefer running sql/001_schema.sql + 002_security_firewall.sql
    + 003_analytics_views.sql as the authoritative Phase 1 DDL; metadata.create_all
    is the portable fallback used by the demo tier and tests.
    """
    from app.models import Base  # noqa: F401  (imports every model)

    Base.metadata.create_all(bind=engine)
    apply_column_migrations()

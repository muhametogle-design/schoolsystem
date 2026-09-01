"""Database engine, portable schema bootstrap, and additive demo migrations."""

from __future__ import annotations

import os
import re
import string
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
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


def set_rls_context(db: Session, *, school_id: int | None, role: str) -> None:
    """Set the PostgreSQL tenant context for the current trusted DB session.

    Route authentication derives both values from a verified JWT and validates
    them against the database user record. SQLite has no RLS session settings,
    so it continues to rely on the same route-level tenant predicates.
    """
    if IS_SQLITE:
        return
    db.execute(
        text("SELECT set_config('app.school_id', :school_id, false)"),
        {"school_id": str(school_id) if school_id is not None else ""},
    )
    db.execute(text("SELECT set_config('app.role', :role, false)"), {"role": role or "none"})


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped session with a deny-by-default RLS context."""
    db = SessionLocal()
    try:
        # A pooled PostgreSQL connection can retain session settings after a
        # commit. Reset before every request, then get_current_user replaces
        # this deny-by-default context with the authenticated user context.
        set_rls_context(db, school_id=None, role="none")
        yield db
    finally:
        db.close()


#: Columns introduced after the original release. ``create_all`` only creates
#: missing *tables*, never missing columns. Keep these migrations additive so a
#: school running the SQLite tier can upgrade without discarding its records.
COLUMN_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("users", "staff_identifier", "VARCHAR(30)"),
    ("users", "phone", "VARCHAR(50)"),
    ("users", "qualifications", "TEXT"),
    ("users", "designation", "VARCHAR(100)"),
    ("users", "bio", "TEXT"),
    ("users", "is_active", "BOOLEAN DEFAULT 1"),
    ("users", "staff_pin_hash", "VARCHAR(255)"),
    ("users", "is_department_head", "BOOLEAN DEFAULT 0"),
    ("users", "photo_data", "TEXT"),
    ("private_schools", "school_code", "VARCHAR(2)"),
    ("private_schools", "design_config", "TEXT"),
    ("private_schools", "billing_contact_name", "VARCHAR(255)"),
    ("private_schools", "billing_phone", "VARCHAR(50)"),
    ("private_schools", "billing_email", "VARCHAR(255)"),
    ("private_schools", "billing_address", "TEXT"),
    ("private_schools", "billing_notes", "TEXT"),
    ("students", "roll_number", "VARCHAR(30)"),
    ("students", "physical_address", "TEXT"),
    ("students", "fee_status", "VARCHAR(20) DEFAULT 'NOT_PAID'"),
    ("students", "photo_data", "TEXT"),
)

# The requested initial estate has fixed, meaningful codes. Older databases
# with unrelated schools receive a collision-free two-letter fallback instead.
_KNOWN_SCHOOL_CODES = {
    "Ilays Educational Academy": "IL",
    "Muse Yusuf Secondary School": "MY",
    "Nugaal High School": "NG",
    "ALQALAM SCHOOLS": "AQ",
    "Las Anod Boarding Secondary School (LBSS)": "LB",
}


def _existing_columns(connection, table: str) -> set[str]:
    """Column names currently present on ``table`` (SQLite + PostgreSQL)."""
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


def _execute_params(connection, statement: str, params: tuple) -> None:
    """Run DBAPI parameterized SQL with the placeholder syntax for this tier."""
    if IS_SQLITE:
        connection.exec_driver_sql(statement.replace("%s", "?"), params)
    else:
        connection.exec_driver_sql(statement, params)


def _allocate_legacy_code(name: str, used: set[str]) -> str:
    known = _KNOWN_SCHOOL_CODES.get(name)
    if known and known not in used:
        return known
    words = re.findall(r"[A-Za-z]+", name.upper())
    letters = "".join(words)
    candidates: list[str] = []
    if len(words) >= 2:
        candidates.append(words[0][0] + words[1][0])
    if len(letters) >= 2:
        candidates.append(letters[:2])
    for candidate in candidates:
        if candidate not in used:
            return candidate
    for first in string.ascii_uppercase:
        for second in string.ascii_uppercase:
            candidate = first + second
            if candidate not in used:
                return candidate
    raise RuntimeError("All two-letter school codes are exhausted")


def _backfill_identity_columns(connection) -> None:
    """Populate non-null values required by the current tenant architecture."""
    if _table_exists(connection, "users") and "is_active" in _existing_columns(connection, "users"):
        connection.exec_driver_sql("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
    if _table_exists(connection, "students") and "fee_status" in _existing_columns(connection, "students"):
        connection.exec_driver_sql("UPDATE students SET fee_status = 'NOT_PAID' WHERE fee_status IS NULL")
    if not _table_exists(connection, "private_schools"):
        return

    school_columns = _existing_columns(connection, "private_schools")
    if "school_code" not in school_columns:
        return
    schools = connection.exec_driver_sql(
        "SELECT id, school_name, school_code FROM private_schools ORDER BY id"
    ).fetchall()
    used = {str(row[2]).upper() for row in schools if row[2]}
    school_codes: dict[int, str] = {}
    for school_id, school_name, school_code in schools:
        code = str(school_code).upper() if school_code else _allocate_legacy_code(str(school_name), used)
        used.add(code)
        school_codes[int(school_id)] = code
        if school_code != code:
            _execute_params(
                connection,
                "UPDATE private_schools SET school_code = %s WHERE id = %s",
                (code, school_id),
            )

    if not _table_exists(connection, "students") or "roll_number" not in _existing_columns(connection, "students"):
        return
    students = connection.exec_driver_sql(
        "SELECT id, school_id, roll_number FROM students ORDER BY school_id, id"
    ).fetchall()
    next_by_school: dict[int, int] = {}
    for student_id, school_id, roll_number in students:
        school_id = int(school_id)
        code = school_codes.get(school_id, "SS")
        next_value = next_by_school.get(school_id, 10000)
        if roll_number:
            match = re.fullmatch(r"[A-Z]{2}-(\d+)", str(roll_number).upper())
            if match:
                next_value = max(next_value, int(match.group(1)) + 1)
        else:
            roll_number = f"{code}-{next_value}"
            _execute_params(
                connection,
                "UPDATE students SET roll_number = %s WHERE id = %s",
                (roll_number, student_id),
            )
            next_value += 1
        next_by_school[school_id] = next_value


def _create_identity_indexes(connection) -> None:
    """Create portable uniqueness/search indexes after legacy rows are filled."""
    if _table_exists(connection, "private_schools") and "school_code" in _existing_columns(connection, "private_schools"):
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_private_schools_school_code_unique "
            "ON private_schools(school_code)"
        )
    if _table_exists(connection, "students") and "roll_number" in _existing_columns(connection, "students"):
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_students_roll_number_unique ON students(roll_number)"
        )


def apply_column_migrations() -> None:
    """Idempotently add missing columns and backfill architecture-required IDs."""
    with engine.begin() as connection:
        # Bootstrap upgrades are a trusted operator operation. This also lets
        # an already-hardened PostgreSQL database backfill additive columns.
        if not IS_SQLITE:
            connection.execute(text("SELECT set_config('app.school_id', '', true)"))
            connection.execute(text("SELECT set_config('app.role', 'state_admin', true)"))
        for table, column, ddl in COLUMN_MIGRATIONS:
            if not _table_exists(connection, table):
                continue
            if column in _existing_columns(connection, table):
                continue
            connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        _backfill_identity_columns(connection)
        _create_identity_indexes(connection)


def init_db() -> None:
    """Bootstrap the portable SQLite tier only.

    PostgreSQL is deliberately schema-managed by ``sql/001_schema.sql`` and
    ``sql/002_security_firewall.sql``. A least-privilege runtime role must not
    own tables or receive accidental DDL rights merely because the API starts.
    """
    if not IS_SQLITE:
        return
    from app.models import Base  # noqa: F401  (imports every model)

    Base.metadata.create_all(bind=engine)
    apply_column_migrations()
    # Module 4: install the row-level change-capture triggers that feed the
    # JSON delta export (SQLite tier bootstraps its own schema; PostgreSQL is
    # handled by sql/004_ops_modules.sql).
    from app.services.backup import install_sqlite_change_triggers

    with engine.begin() as connection:
        install_sqlite_change_triggers(connection)

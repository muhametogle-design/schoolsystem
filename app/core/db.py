"""SQLAlchemy engine/session factories.

The application always opens connections with a session-local ``campus_id``,
``role`` and ``user_id`` set in Postgres so Row-Level-Security policies in
``sql/001_schema.sql`` restrict every read/write to the calling tenant.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Optional[Engine] = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            future=True,
        )
    return _engine


def get_sessionmaker() -> sessionmaker:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def set_session_tenancy(
    session: Session,
    campus_id: uuid.UUID,
    *,
    role: str = "anonymous",
    user_id: Optional[uuid.UUID] = None,
) -> None:
    """Bake the calling tenant into the Postgres transaction (RLS context)."""

    for cfg_name, value in (
        ("neemis.campus_id", str(campus_id) if campus_id else None),
        ("neemis.role", role),
        ("neemis.user_id", str(user_id) if user_id else None),
    ):
        # set_config(..., true) is transaction-local, which is exactly what we
        # want for the lifetime of one request/transaction.
        session.execute(
            text("SELECT set_config(:name, coalesce(:value, ''), true)"),
            {"name": cfg_name, "value": value or ""},
        )


@contextmanager
def tenant_session(
    campus_id: uuid.UUID,
    *,
    role: str = "anonymous",
    user_id: Optional[uuid.UUID] = None,
) -> Iterator[Session]:
    """Context-managed session with RLS context applied."""
    factory = get_sessionmaker()
    with factory() as session:
        set_session_tenancy(session, campus_id, role=role, user_id=user_id)
        try:
            yield session
        finally:
            session.close()

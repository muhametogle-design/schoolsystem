"""Tiny SQLite-backed store for the container demo endpoints.

Used only when ``NEEMIS_DEMO_MODE=true``. It is intentionally small and
dependency-free so the single-container build (Python 3.13-slim) can persist
the ``/students`` list/add without provisioning PostgreSQL.

For the full guarded system (RLS + JWT + central aggregation) the real
backend is PostgreSQL — see ``sql/`` and ``app/models/``.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id            TEXT PRIMARY KEY,
    ne_sid        TEXT UNIQUE NOT NULL,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    gender        TEXT NOT NULL,
    dob           TEXT NOT NULL,
    grade_level   TEXT,
    status        TEXT NOT NULL DEFAULT 'active',
    matriculated_on TEXT NOT NULL,
    campus_code   TEXT DEFAULT 'DEMO',
    created_at    TEXT NOT NULL
);
"""

_SEED = [
    {
        "first_name": "Amina",
        "last_name": "Yusuf",
        "gender": "female",
        "dob": "2012-04-12",
        "grade_level": "SS1-A",
        "campus_code": "DEMO",
    },
    {
        "first_name": "Ibrahim",
        "last_name": "Musa",
        "gender": "male",
        "dob": "2011-09-03",
        "grade_level": "SS2-B",
        "campus_code": "DEMO",
    },
]


class DemoStore:
    """Thread-light SQLite wrapper for the demo endpoints."""

    def __init__(self, db_path: str | None = None) -> None:
        raw = db_path or settings.demo_db_path
        self.path = Path(raw)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._setup()

    def _setup(self) -> None:
        with self.conn:
            self.conn.executescript(_SCHEMA)
            count = self.conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            if count == 0:
                for row in _SEED:
                    self._insert_row(self._build_row(row))

    @staticmethod
    def _build_row(data: Dict[str, Any]) -> Dict[str, Any]:
        now = date.today().isoformat()
        student_id = str(uuid.uuid4())
        return {
            "id": student_id,
            "ne_sid": "NE-SID-" + student_id.replace("-", ""),
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "gender": data["gender"],
            "dob": data["dob"],
            "grade_level": data.get("grade_level") or "",
            "status": data.get("status", "active"),
            "matriculated_on": now,
            "campus_code": data.get("campus_code", "DEMO"),
            "created_at": now,
        }

    def _insert_row(self, row: Dict[str, Any]) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO students
                  (id, ne_sid, first_name, last_name, gender, dob, grade_level,
                   status, matriculated_on, campus_code, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["ne_sid"],
                    row["first_name"],
                    row["last_name"],
                    row["gender"],
                    row["dob"],
                    row["grade_level"],
                    row["status"],
                    row["matriculated_on"],
                    row["campus_code"],
                    row["created_at"],
                ),
            )

    def list_students(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM students ORDER BY last_name, first_name"
        ).fetchall()
        cols = [c[0] for c in self.conn.execute("SELECT * FROM students LIMIT 0").description]
        return [dict(zip(cols, r)) for r in rows]

    def get_student(self, student_id: str) -> Dict[str, Any] | None:
        # Accept either the internal uuid or the public NE-SID string.
        row = self.conn.execute(
            "SELECT * FROM students WHERE id = ? OR ne_sid = ?", (student_id, student_id)
        ).fetchone()
        if row is None:
            return None
        cols = [c[0] for c in self.conn.execute("SELECT * FROM students LIMIT 0").description]
        return dict(zip(cols, row))

    def add_student(self, data: Dict[str, Any]) -> Dict[str, Any]:
        row = self._build_row(data)
        self._insert_row(row)
        return row


_store: DemoStore | None = None


def get_demo_store() -> DemoStore:
    global _store
    if _store is None:
        _store = DemoStore()
    return _store

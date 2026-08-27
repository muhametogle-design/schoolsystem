"""Unit tests for Phase 1 ingestion validation."""

from __future__ import annotations

from app.services.ingestion import validate_attendance_row, validate_batch


def test_attendance_valid():
    row = {
        "student_id": "11111111-1111-1111-1111-111111111111",
        "course_section_id": "22222222-2222-2222-2222-222222222222",
        "attendance_date": "2026-08-27",
        "status": "present",
        "hours": 6,
    }
    result = validate_attendance_row(row, row_id=1)
    assert result.passed is True
    assert result.errors == []


def test_attendance_invalid_status_and_date():
    row = {
        "student_id": "11111111-1111-1111-1111-111111111111",
        "attendance_date": "not-a-date",
        "status": "maybe",
        "hours": 30,
    }
    result = validate_attendance_row(row, row_id=1)
    assert result.passed is False
    assert "status" in result.errors
    assert "attendance_date" in result.errors
    assert "hours" in result.errors


def test_batch_counts_accepts_only_good_rows():
    good = {
        "student_id": "11111111-1111-1111-1111-111111111111",
        "attendance_date": "2026-08-27",
        "status": "present",
        "hours": 6,
    }
    bad = {
        "student_id": "1",
        "attendance_date": "2026-08-27",
        "status": "present",
        "hours": 6,
    }
    results, accepted = validate_batch("attendance", [good, bad])
    assert accepted == 1
    assert results[0].passed is True
    assert results[1].passed is False

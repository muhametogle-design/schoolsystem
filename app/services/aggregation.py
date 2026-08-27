"""Phase 3 Overnight Aggregation Engine.

Consumes dean-locked campus datasets and rebuilds the **central** state
registries:
  * ``central.student_registry`` — schooling history tree, GPA trend.
  * ``central.teacher_registry`` — qualifications, certifications, payroll.

Every batch is idempotent by ``snapshot_key`` (batch date + phase) and writes
an ``aggregation_batches`` audit row, so re-runs cannot double-count.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.models.academics import Transcript
from app.models.audit import (
    AggregationBatch,
    CentralKpiRollup,
    CentralStudentRegistry,
    CentralTeacherRegistry,
)
from app.models.identity import Campus
from app.models.registry import Student, StudentMobility
from app.models.teachers import (
    Teacher,
    TeacherCertification,
    TeacherPayrollProfile,
    TeacherQualification,
)


def _snapshot_key(batch_date: date, phase: int, campus_id: Optional[uuid.UUID] = None) -> str:
    tail = f":{campus_id}" if campus_id else ":ALL"
    return f"{batch_date.isoformat()}:{phase}{tail}"


def _as_numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def aggregate_students(
    session: Session,
    *,
    batch_date: date,
    limit: int = 10_000,
) -> int:
    """Build the central student registry for the given batch date."""
    upserted = 0
    students = session.execute(
        select(Student).where(Student.status != "deceased").order_by(Student.id).limit(limit)
    ).scalars().all()

    # All mobility edges per student, chronologically ordered.
    edges_by_student: Dict[uuid.UUID, List[StudentMobility]] = defaultdict(list)
    for mob in session.execute(
        select(StudentMobility).order_by(StudentMobility.requested_on, StudentMobility.created_at)
    ).scalars().all():
        edges_by_student[mob.student_id].append(mob)

    transcripts_by_student: Dict[uuid.UUID, List[Transcript]] = defaultdict(list)
    for tr in session.execute(
        select(Transcript).order_by(Transcript.academic_year_id, Transcript.term_id)
    ).scalars().all():
        transcripts_by_student[tr.student_id].append(tr)

    for student in students:
        history = [
            {
                "mobility_id": str(e.id),
                "edge_type": e.edge_type,
                "from_campus_id": str(e.from_campus_id) if e.from_campus_id else None,
                "to_campus_id": str(e.to_campus_id),
                "transfer_state": e.transfer_state,
                "effective_on": e.effective_on.isoformat() if e.effective_on else None,
            }
            for e in edges_by_student.get(student.id, [])
        ]
        gpa_trend = [
            {
                "academic_year_id": str(t.academic_year_id),
                "term_id": str(t.term_id) if t.term_id else None,
                "gpa": _as_numeric(t.cumulative_gpa),
                "credits": _as_numeric(t.credits_earned),
                "inherited": t.is_inherited,
            }
            for t in transcripts_by_student.get(student.id, [])
        ]
        key = _snapshot_key(batch_date, 3, student.campus_id)
        row = session.scalar(
            select(CentralStudentRegistry).where(
                CentralStudentRegistry.student_id == student.id
            )
        )
        if row is None:
            row = CentralStudentRegistry(
                student_id=student.id,
                ne_sid=student.ne_sid,
                current_campus_id=student.campus_id,
                snapshot_key=key,
            )
            session.add(row)
        # Mutate with no `updated_at` on these central tables: overwrite and
        # note aggregated_at in the snapshot.
        row.current_campus_id = student.campus_id
        row.schooling_history = history
        row.gpa_trend = gpa_trend
        row.latest_enrollment = {
            "status": student.status,
            "grade_level": student.current_grade_level,
            "major": student.current_major,
        }
        row.aggregated_at = datetime.now(timezone.utc)
        row.snapshot_key = key
        upserted += 1
    session.flush()
    return upserted


def aggregate_teachers(
    session: Session,
    *,
    batch_date: date,
    limit: int = 10_000,
) -> int:
    upserted = 0
    teachers = session.execute(
        select(Teacher).order_by(Teacher.id).limit(limit)
    ).scalars().all()

    quals_by_teacher: Dict[uuid.UUID, List[TeacherQualification]] = defaultdict(list)
    for q in session.execute(select(TeacherQualification)).scalars().all():
        quals_by_teacher[q.teacher_id].append(q)

    certs_by_teacher: Dict[uuid.UUID, List[TeacherCertification]] = defaultdict(list)
    for c in session.execute(select(TeacherCertification)).scalars().all():
        certs_by_teacher[c.teacher_id].append(c)

    profiles = {
        p.teacher_id: p for p in session.execute(select(TeacherPayrollProfile)).scalars().all()
    }

    for teacher in teachers:
        key = _snapshot_key(batch_date, 3, teacher.campus_id)
        row = session.scalar(
            select(CentralTeacherRegistry).where(
                CentralTeacherRegistry.teacher_id == teacher.id
            )
        )
        if row is None:
            row = CentralTeacherRegistry(
                teacher_id=teacher.id,
                ne_tid=teacher.ne_tid,
                current_campus_id=teacher.campus_id,
                status=teacher.employment_state,
                snapshot_key=key,
            )
            session.add(row)
        row.current_campus_id = teacher.campus_id
        row.status = teacher.employment_state
        row.qualifications = [
            {
                "id": str(q.id),
                "degree_level": q.degree_level,
                "field_of_study": q.field_of_study,
                "institution": q.institution,
                "awarded_year": q.awarded_year,
            }
            for q in quals_by_teacher.get(teacher.id, [])
        ]
        row.certifications = [
            {
                "id": str(c.id),
                "cert_kind": c.cert_kind,
                "cert_no": c.cert_no,
                "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
                "status": c.status,
            }
            for c in certs_by_teacher.get(teacher.id, [])
        ]
        p = profiles.get(teacher.id)
        row.payroll_profile = (
            {
                "grade_tier": p.grade_tier,
                "hardship_zone": p.hardship_zone,
                "regional_allowance": _as_numeric(p.regional_allowance),
                "pension_rate": _as_numeric(p.pension_rate),
                "tin": p.tin,
                "is_bank_verified": p.is_bank_verified,
            }
            if p
            else None
        )
        row.aggregated_at = datetime.now(timezone.utc)
        row.snapshot_key = key
        upserted += 1
    session.flush()
    return upserted


def run_overnight_batch(
    session: Session,
    *,
    batch_date: date,
    limit: int = 10_000,
) -> Dict[str, Any]:
    batch = AggregationBatch(batch_date=batch_date, phase=3, batch_state="running")
    batch.started_at = datetime.now(timezone.utc)
    session.add(batch)
    session.flush()

    try:
        students = aggregate_students(session, batch_date=batch_date, limit=limit)
        teachers = aggregate_teachers(session, batch_date=batch_date, limit=limit)
        batch.batch_state = "completed"
        batch.stats = {
            "students_upserted": students,
            "teachers_upserted": teachers,
            "batch_date": batch_date.isoformat(),
        }
        session.add(batch)
        session.flush()
        return batch.stats
    except Exception as exc:  # noqa: BLE001
        # Keep the original batch object in the same transaction so a caller
        # can review the failure; the caller decides whether to commit/rollback.
        batch.batch_state = "failed"
        batch.error = str(exc)
        session.add(batch)
        session.flush()
        raise

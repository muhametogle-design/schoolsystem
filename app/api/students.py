"""Student Registry & Mobility Matrix endpoints.

Two modes:
  * demo mode (NEEMIS_DEMO_MODE=true): unauthenticated /students GET/POST
    backed by the local SQLite DemoStore — ideal for container exploration.
  * production mode: RLS scoped JWT access to the PostgreSQL tables.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import campus_context, get_principal, get_session
from app.core.config import settings
from app.core.demo_store import get_demo_store
from app.core.tenancy import Principal
from app.models.registry import Enrollment, Student, StudentMobility
from app.schemas.students import MobilityCreate, MobilityOut, StudentCreate, StudentOut

router = APIRouter(prefix="/students", tags=["student-registry"])

if settings.demo_mode:

    @router.get("")
    def list_students_demo() -> List[Dict[str, Any]]:
        """List students (demo mode, no auth, SQLite-backed)."""
        return get_demo_store().list_students()

    @router.get("/{student_id}")
    def get_student_demo(student_id: str) -> Dict[str, Any]:
        """Look up one student by uuid or NE-SID (demo mode)."""
        row = get_demo_store().get_student(student_id)
        if row is None:
            raise HTTPException(404, "Student not found")
        return row

    @router.post("", status_code=201)
    def add_student_demo(body: StudentCreate) -> Dict[str, Any]:
        """Add a student (demo mode, no auth, SQLite-backed)."""
        store = get_demo_store()
        row = store.add_student(
            {
                "first_name": body.first_name,
                "last_name": body.last_name,
                "gender": body.gender,
                "dob": body.dob.isoformat(),
                "grade_level": body.current_grade_level,
                "campus_code": body.current_major or "DEMO",
            }
        )
        return row

else:

    @router.post("", response_model=StudentOut, status_code=201)
    def register_student(
        body: StudentCreate,
        campus_id: uuid.UUID = Depends(campus_context),
        principal: Principal = Depends(get_principal),
        session: Session = Depends(get_session),
    ):
        if principal.role not in ("clerk", "dean"):
            raise HTTPException(403, "Only clerks or deans may register students")
        student = Student(
            campus_id=campus_id,
            first_name=body.first_name,
            middle_name=body.middle_name,
            last_name=body.last_name,
            dob=body.dob,
            gender=body.gender,
            enrollment_kind=body.enrollment_kind,
            current_major=body.current_major,
            current_grade_level=body.current_grade_level,
            guardian_name=body.guardian_name,
            guardian_phone=body.guardian_phone,
            status="active",
            matriculated_on=body.dob,
        )
        if body.coordinates:
            student.coordinates = "(" + ",".join(str(x) for x in body.coordinates) + ")"
        session.add(student)
        session.flush()
        session.refresh(student)  # fetch NE-SID set by DB trigger
        return student

    @router.get("", response_model=List[StudentOut])
    def list_students(
        campus_id: uuid.UUID = Depends(campus_context),
        session: Session = Depends(get_session),
        status_: str = Query(default="active", alias="status"),
    ):
        rows = session.scalars(
            select(Student)
            .where(Student.campus_id == campus_id, Student.status == status_)
            .order_by(Student.last_name, Student.first_name)
        ).all()
        return rows


@router.get("/{student_id}", response_model=StudentOut)
def get_student(
    student_id: uuid.UUID,
    campus_id: uuid.UUID = Depends(campus_context),
    session: Session = Depends(get_session),
):
    row = session.scalar(
        select(Student).where(Student.id == student_id, Student.campus_id == campus_id)
    )
    if row is None:
        raise HTTPException(404, "Student not found in this campus")
    return row


@router.get("/{student_id}/mobility", response_model=List[MobilityOut])
def student_mobility_history(
    student_id: uuid.UUID,
    campus_id: uuid.UUID = Depends(campus_context),
    session: Session = Depends(get_session),
):
    rows = session.scalars(
        select(StudentMobility)
        .where(StudentMobility.student_id == student_id)
        .order_by(StudentMobility.requested_on.desc())
    ).all()
    return rows


@router.post("/{student_id}/mobility", response_model=MobilityOut, status_code=201)
def record_transfer(
    student_id: uuid.UUID,
    body: MobilityCreate,
    campus_id: uuid.UUID = Depends(campus_context),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    if principal.role not in ("dean", "state_admin", "system"):
        raise HTTPException(403, "Transfer requests require dean or state approval")
    mob = StudentMobility(
        student_id=student_id,
        campus_id=campus_id,
        from_campus_id=campus_id,
        to_campus_id=body.to_campus_id,
        from_enrollment_id=body.from_enrollment_id,
        to_enrollment_id=None,
        previous_mobility_id=body.previous_mobility_id,
        edge_type=body.edge_type,
        transfer_state="drafted",
        requested_on=body.requested_on,
        effective_on=body.effective_on,
        notes=body.notes,
    )
    session.add(mob)
    session.flush()
    # Chronological history is inherited by the aggregation read model from
    # the student_mobility tree, including transcripts/GPA/behaviour/truancy.
    return mob

"""THE EXAM DATA RELEASE VALVE.

Schools retain complete privacy while structuring or drafting student marks.
Nothing reaches the government analytics portal until a school administrator
officially hits "Publish Exam Marks to State", which:

  1. flips student_grades.is_published => TRUE for the released scope,
  2. registers an IMMUTABLE exam_submission_events record,
  3. streams an `exam_published` event to state dashboards over WebSockets.

Publication is irreversible: the draft valve only opens one way.
"""

from __future__ import annotations

import datetime as dt

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ws import manager
from app.models import ExamSubmissionEvent, SchoolClass, StudentGrade, Subject


class PublicationError(HTTPException):
    pass


def publish_exam_marks(
    database_session: Session,
    *,
    school_id: int,
    class_id: int,
    subject_id: int,
    academic_year_id: int,
    exam_name: str,
    published_by: int,
) -> dict:
    # Verify the requested scope actually belongs to this tenant school.
    klass = database_session.execute(
        select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.school_id == school_id)
    ).scalar_one_or_none()
    subject = database_session.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    ).scalar_one_or_none()
    if not klass or not subject:
        raise PublicationError(404, "Class or subject not found for this school.")

    scope = {
        "school_id": school_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "academic_year_id": academic_year_id,
        "exam_name": exam_name,
    }
    grades = database_session.execute(select(StudentGrade).filter_by(**scope)).scalars().all()
    if not grades:
        raise PublicationError(404, "No exam marks found for this release scope.")

    existing_event = database_session.execute(
        select(ExamSubmissionEvent).where(
            ExamSubmissionEvent.school_id == school_id,
            ExamSubmissionEvent.class_id == class_id,
            ExamSubmissionEvent.subject_id == subject_id,
            ExamSubmissionEvent.academic_year_id == academic_year_id,
            ExamSubmissionEvent.exam_name == exam_name,
        )
    ).scalar_one_or_none()
    if existing_event:
        raise PublicationError(
            409,
            "This exam scope was already published to the State. "
            "exam_submission_events are immutable and cannot be re-issued.",
        )

    drafts = [g for g in grades if not g.is_published]
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    for grade in drafts:
        grade.is_published = True
        grade.updated_at = now

    event = ExamSubmissionEvent(
        school_id=school_id,
        class_id=class_id,
        subject_id=subject_id,
        academic_year_id=academic_year_id,
        exam_name=exam_name,
        records_released=len(drafts),
        published_by=published_by,
        published_at=now,
    )
    database_session.add(event)
    database_session.commit()

    payload = {
        "school_id": school_id,
        "class_id": class_id,
        "class_label": f"{klass.class_level} {klass.class_stream}",
        "subject": subject.subject_name,
        "exam_name": exam_name,
        "records_released": len(drafts),
        "event_id": event.id,
    }
    manager.broadcast_sync("exam_published", payload)
    return payload

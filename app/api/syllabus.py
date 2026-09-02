"""SYLLABUS COMPLETION MODULE — manager-owned CRUD over classes 1-12.

School Managers fully control topic lists, target completion percentages,
term deadlines and manual progress overrides. Teachers get read-only
visibility (scoped to the tenant) so they can see delivery expectations.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_school
from app.core.db import get_db
from app.core.ws import manager as ws_manager
from app.models import (
    CLASS_LEVELS,
    SchoolClass,
    Subject,
    SyllabusPlan,
    SyllabusTopic,
    User,
)
from app.schemas import (
    SyllabusPlanCreate,
    SyllabusPlanUpdate,
    SyllabusTopicCreate,
    SyllabusTopicUpdate,
    TopicsCoveredRequest,
)

router = APIRouter(prefix="/api/v1/school/syllabus", tags=["syllabus"])

any_school_user = require_school()
manager_only = require_school("school_manager")


def _class_label(klass: SchoolClass | None) -> str | None:
    return f"{klass.class_level} {klass.class_stream}" if klass else None


def _plan_or_404(db: Session, school_id: int, plan_id: int) -> SyllabusPlan:
    plan = (
        db.query(SyllabusPlan)
        .options(joinedload(SyllabusPlan.topics))
        .filter_by(id=plan_id, school_id=school_id)
        .one_or_none()
    )
    if not plan:
        raise HTTPException(404, "Syllabus plan not found in this school")
    return plan


def _topic_or_404(db: Session, school_id: int, topic_id: int) -> SyllabusTopic:
    topic = db.query(SyllabusTopic).filter_by(id=topic_id, school_id=school_id).one_or_none()
    if not topic:
        raise HTTPException(404, "Syllabus topic not found in this school")
    return topic


def _serialize_topic(topic: SyllabusTopic) -> dict:
    return {
        "id": topic.id,
        "unit_code": topic.unit_code,
        "title": topic.title,
        "sort_order": topic.sort_order,
        "is_covered": bool(topic.is_covered),
        "covered_at": topic.covered_at.isoformat() if topic.covered_at else None,
    }


def _serialize_plan(plan: SyllabusPlan, klass: SchoolClass | None, subject: Subject | None) -> dict:
    topics = sorted(plan.topics, key=lambda t: (t.sort_order, t.id))
    covered = sum(1 for t in topics if t.is_covered)
    computed = round(covered / len(topics) * 100) if topics else 0
    effective = plan.progress_override_pct if plan.progress_override_pct is not None else computed
    days_left = (plan.term_deadline - dt.date.today()).days if plan.term_deadline else None
    return {
        "id": plan.id,
        "class_id": plan.class_id,
        "class_label": _class_label(klass),
        "class_level": klass.class_level if klass else None,
        "subject_id": plan.subject_id,
        "subject_name": subject.subject_name if subject else None,
        "subject_code": subject.subject_code if subject else None,
        "term_name": plan.term_name,
        "target_completion_pct": plan.target_completion_pct,
        "term_deadline": plan.term_deadline.isoformat() if plan.term_deadline else None,
        "days_to_deadline": days_left,
        "notes": plan.notes,
        "topics_total": len(topics),
        "topics_covered": covered,
        "computed_progress_pct": computed,
        "progress_override_pct": plan.progress_override_pct,
        "effective_progress_pct": effective,
        "on_track": effective >= plan.target_completion_pct,
        "topics": [_serialize_topic(t) for t in topics],
    }


def _emit_syllabus_change(school_id: int, action: str) -> None:
    ws_manager.broadcast_sync("syllabus_changed", {"school_id": school_id, "action": action})


# --------------------------------------------------------------------------- #
# Read — every tenant role (teachers are read-only by route method gating)
# --------------------------------------------------------------------------- #
@router.get("")
def list_syllabus(
    class_level: str | None = Query(default=None),
    class_id: int | None = Query(default=None),
    user: User = Depends(any_school_user),
    db: Session = Depends(get_db),
):
    if class_level and class_level not in CLASS_LEVELS:
        raise HTTPException(422, f"class_level must be one of {', '.join(CLASS_LEVELS)}")

    query = (
        db.query(SyllabusPlan, SchoolClass, Subject)
        .join(SchoolClass, SyllabusPlan.class_id == SchoolClass.id)
        .join(Subject, SyllabusPlan.subject_id == Subject.id)
        .options(joinedload(SyllabusPlan.topics))
        .filter(SyllabusPlan.school_id == user.school_id)
    )
    if class_level:
        query = query.filter(SchoolClass.class_level == class_level)
    if class_id:
        query = query.filter(SyllabusPlan.class_id == class_id)

    rows = query.all()
    plans = [_serialize_plan(plan, klass, subject) for plan, klass, subject in rows]
    plans.sort(key=lambda p: (int((p["class_level"] or "Class 99").rsplit(" ", 1)[-1]), p["subject_name"] or "", p["term_name"]))
    return {
        "plans": plans,
        "can_edit": user.role == "school_manager",
        "class_levels": list(CLASS_LEVELS),
    }


# --------------------------------------------------------------------------- #
# Manager-only CRUD
# --------------------------------------------------------------------------- #
@router.post("", status_code=status.HTTP_201_CREATED)
def create_plan(payload: SyllabusPlanCreate, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    klass = db.query(SchoolClass).filter_by(id=payload.class_id, school_id=user.school_id).one_or_none()
    if not klass:
        raise HTTPException(404, "Class not found in this school")
    subject = db.query(Subject).filter_by(id=payload.subject_id, school_id=user.school_id).one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found in this school")

    duplicate = (
        db.query(SyllabusPlan)
        .filter_by(
            school_id=user.school_id,
            class_id=payload.class_id,
            subject_id=payload.subject_id,
            term_name=payload.term_name,
        )
        .one_or_none()
    )
    if duplicate:
        raise HTTPException(409, f"A {payload.term_name} syllabus for this class subject already exists")

    plan = SyllabusPlan(
        school_id=user.school_id,
        class_id=payload.class_id,
        subject_id=payload.subject_id,
        term_name=payload.term_name,
        target_completion_pct=payload.target_completion_pct,
        term_deadline=payload.term_deadline,
        notes=payload.notes,
    )
    db.add(plan)
    db.flush()
    for index, topic in enumerate(payload.topics):
        db.add(
            SyllabusTopic(
                school_id=user.school_id,
                plan_id=plan.id,
                unit_code=topic.unit_code,
                title=topic.title,
                sort_order=topic.sort_order or index,
            )
        )
    db.commit()
    db.refresh(plan)
    _emit_syllabus_change(user.school_id, "plan_created")
    return {"plan": _serialize_plan(plan, klass, subject)}


@router.patch("/{plan_id}")
def update_plan(
    plan_id: int,
    payload: SyllabusPlanUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    plan = _plan_or_404(db, user.school_id, plan_id)
    updates = payload.model_dump(exclude_unset=True)

    if "term_name" in updates and updates["term_name"]:
        duplicate = (
            db.query(SyllabusPlan)
            .filter(
                SyllabusPlan.school_id == user.school_id,
                SyllabusPlan.class_id == plan.class_id,
                SyllabusPlan.subject_id == plan.subject_id,
                SyllabusPlan.term_name == updates["term_name"],
                SyllabusPlan.id != plan.id,
            )
            .one_or_none()
        )
        if duplicate:
            raise HTTPException(409, "Another plan already covers that term for this class subject")
        plan.term_name = updates["term_name"]
    if "target_completion_pct" in updates and updates["target_completion_pct"] is not None:
        plan.target_completion_pct = updates["target_completion_pct"]
    if payload.clear_term_deadline:
        plan.term_deadline = None
    elif "term_deadline" in updates and updates["term_deadline"] is not None:
        plan.term_deadline = updates["term_deadline"]
    if payload.clear_progress_override:
        plan.progress_override_pct = None
    elif "progress_override_pct" in updates and updates["progress_override_pct"] is not None:
        plan.progress_override_pct = updates["progress_override_pct"]
    if "notes" in updates:
        plan.notes = updates["notes"]

    db.commit()
    db.refresh(plan)
    klass = db.get(SchoolClass, plan.class_id)
    subject = db.get(Subject, plan.subject_id)
    _emit_syllabus_change(user.school_id, "plan_updated")
    return {"plan": _serialize_plan(plan, klass, subject)}


@router.delete("/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    plan = _plan_or_404(db, user.school_id, plan_id)
    db.delete(plan)
    db.commit()
    _emit_syllabus_change(user.school_id, "plan_deleted")
    return {"deleted": plan_id}


@router.post("/{plan_id}/topics", status_code=status.HTTP_201_CREATED)
def add_topic(
    plan_id: int,
    payload: SyllabusTopicCreate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    plan = _plan_or_404(db, user.school_id, plan_id)
    topic = SyllabusTopic(
        school_id=user.school_id,
        plan_id=plan.id,
        unit_code=payload.unit_code,
        title=payload.title,
        sort_order=payload.sort_order or len(plan.topics),
    )
    db.add(topic)
    db.commit()
    _emit_syllabus_change(user.school_id, "topic_added")
    return {"topic": _serialize_topic(topic)}


@router.patch("/topics/{topic_id}")
def update_topic(
    topic_id: int,
    payload: SyllabusTopicUpdate,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    topic = _topic_or_404(db, user.school_id, topic_id)
    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates and updates["title"]:
        topic.title = updates["title"]
    if "unit_code" in updates:
        topic.unit_code = updates["unit_code"]
    if "sort_order" in updates and updates["sort_order"] is not None:
        topic.sort_order = updates["sort_order"]
    if "is_covered" in updates and updates["is_covered"] is not None:
        topic.is_covered = updates["is_covered"]
        topic.covered_at = dt.datetime.utcnow() if updates["is_covered"] else None
        topic.covered_by = user.id if updates["is_covered"] else None
    db.commit()
    _emit_syllabus_change(user.school_id, "topic_updated")
    return {"topic": _serialize_topic(topic)}


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    topic = _topic_or_404(db, user.school_id, topic_id)
    db.delete(topic)
    db.commit()
    _emit_syllabus_change(user.school_id, "topic_deleted")
    return {"deleted": topic_id}


@router.post("/{plan_id}/log-covered")
def log_topics_covered(
    plan_id: int,
    payload: TopicsCoveredRequest,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
):
    """'Log Topic Covered' modal — bulk tick specific national curriculum units."""
    plan = _plan_or_404(db, user.school_id, plan_id)
    topics_by_id = {t.id: t for t in plan.topics}
    unknown = [tid for tid in payload.topic_ids if tid not in topics_by_id]
    if unknown:
        raise HTTPException(422, f"Topics {unknown} do not belong to this syllabus plan")

    now = dt.datetime.utcnow()
    for tid in payload.topic_ids:
        topic = topics_by_id[tid]
        topic.is_covered = payload.covered
        topic.covered_at = now if payload.covered else None
        topic.covered_by = user.id if payload.covered else None
    db.commit()
    db.refresh(plan)
    klass = db.get(SchoolClass, plan.class_id)
    subject = db.get(Subject, plan.subject_id)
    _emit_syllabus_change(user.school_id, "topics_logged")
    return {"plan": _serialize_plan(plan, klass, subject)}

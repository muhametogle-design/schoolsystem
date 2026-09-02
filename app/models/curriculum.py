"""Curriculum delivery tier: editable syllabus plans, national curriculum units,
and the tenant design/layout configuration store.

The Syllabus Completion Module is manager-owned (full CRUD): topic lists,
target completion percentages, term deadlines and manual progress overrides.
Teachers receive read-only visibility of the plans for their assigned classes.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

SYLLABUS_TERMS = ("Term 1", "Term 2", "Term 3")


class SyllabusPlan(Base):
    """One subject's syllabus for a class in a term.

    ``progress_override_pct`` lets a School Manager manually override the
    computed completion statistic (covered topics / total topics) when the
    ground truth differs from the ticked units.
    """

    __tablename__ = "syllabus_plans"
    __table_args__ = (
        UniqueConstraint("school_id", "class_id", "subject_id", "term_name", name="uq_syllabus_plan"),
        CheckConstraint(
            "target_completion_pct >= 0 AND target_completion_pct <= 100", name="chk_syllabus_target"
        ),
        CheckConstraint(
            "progress_override_pct IS NULL OR (progress_override_pct >= 0 AND progress_override_pct <= 100)",
            name="chk_syllabus_override",
        ),
        Index("idx_syllabus_plans_school_class", "school_id", "class_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    term_name: Mapped[str] = mapped_column(String(30), nullable=False, default="Term 1")
    target_completion_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    term_deadline: Mapped[dt.date | None] = mapped_column(Date)
    progress_override_pct: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    school_class = relationship("SchoolClass")
    subject = relationship("Subject")
    topics = relationship(
        "SyllabusTopic",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="SyllabusTopic.sort_order, SyllabusTopic.id",
    )


class SyllabusTopic(Base):
    """A national curriculum unit inside a syllabus plan (tick-off tracked)."""

    __tablename__ = "syllabus_topics"
    __table_args__ = (Index("idx_syllabus_topics_plan", "plan_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("syllabus_plans.id", ondelete="CASCADE"), nullable=False)
    unit_code: Mapped[str | None] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_covered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    covered_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    covered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    plan = relationship("SyllabusPlan", back_populates="topics")


class SchoolUiConfig(Base):
    """Published (live) design & layout configuration for a school tenant.

    Managers iterate on drafts client-side ('Save Progress'); 'Push Live'
    persists the JSON document here so every student/teacher session renders
    with the school's chosen accent colour, typography and visible blocks.
    """

    __tablename__ = "school_ui_configs"

    school_id: Mapped[int] = mapped_column(
        ForeignKey("private_schools.id", ondelete="CASCADE"), primary_key=True
    )
    config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

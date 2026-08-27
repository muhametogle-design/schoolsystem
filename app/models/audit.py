"""Phase 2/3 artifacts: record locks, batch jobs, central registries."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CampusScopedMixin
from app.models.types import BatchState, EmploymentState, FundingKind, LockEntity, PayoutState, SignatureScheme

lock_entity_types = (
    "attendance",
    "exam_sheet",
    "grade",
    "payroll_entry",
    "teacher_profile",
    "classroom",
    "course_section",
    "student_record",
)


class RecordLock(Base, CampusScopedMixin):
    """Cryptographic lock record (Phase 2).

    ``payload_hash`` and ``signature`` are the dean's Ed25519 proof of the
    frozen canonical payload. DB trigger ``enforce_record_lock`` uses this row
    to reject later UPDATE/DELETE on the referenced entity.
    """

    __tablename__ = "record_locks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    entity_type: Mapped[str] = mapped_column(LockEntity, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    signature_scheme: Mapped[str] = mapped_column(SignatureScheme, default="ed25519", nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    locked_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.managers.id"), nullable=False
    )
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    unlocked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.managers.id")
    )
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unlock_signature: Mapped[bytes | None] = mapped_column(BYTEA)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.record_locks.id")
    )
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_record_lock_entity"),
    )


class AggregationBatch(Base):
    __tablename__ = "aggregation_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    batch_date: Mapped[date] = mapped_column(Date, nullable=False)
    phase: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_state: Mapped[str] = mapped_column(BatchState, default="queued", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class CentralStudentRegistry(Base):
    __tablename__ = "student_registry"
    __table_args__ = {"schema": "central"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.students.id"), unique=True, nullable=False
    )
    ne_sid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    current_campus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.campus.id"), nullable=False
    )
    schooling_history: Mapped[list] = mapped_column(JSONB, default=list)
    latest_enrollment: Mapped[dict | None] = mapped_column(JSONB)
    gpa_trend: Mapped[list] = mapped_column(JSONB, default=list)
    aggregated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    snapshot_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class CentralTeacherRegistry(Base):
    __tablename__ = "teacher_registry"
    __table_args__ = {"schema": "central"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.teachers.id"), unique=True, nullable=False
    )
    ne_tid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    current_campus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.campus.id"), nullable=False
    )
    qualifications: Mapped[list] = mapped_column(JSONB, default=list)
    certifications: Mapped[list] = mapped_column(JSONB, default=list)
    payroll_profile: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(EmploymentState, nullable=False)
    aggregated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    snapshot_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class CentralFundingPayout(Base):
    __tablename__ = "funding_payouts"
    __table_args__ = {"schema": "central"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    campus_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.campus.id"), nullable=False
    )
    period: Mapped[str] = mapped_column(String, nullable=False)
    funding_kind: Mapped[str] = mapped_column(FundingKind, nullable=False)
    formula: Mapped[dict] = mapped_column(JSONB, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    status: Mapped[str] = mapped_column(PayoutState, default="pending", nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("public.managers.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ledger_ref: Mapped[str | None] = mapped_column(String)
    __table_args__ = (
        UniqueConstraint("campus_id", "period", "funding_kind", name="uq_funding_payout"),
    )


class CentralKpiRollup(Base):
    __tablename__ = "kpi_rollups"
    __table_args__ = {"schema": "central"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    campus_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("public.campus.id"))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("campus_id", "period_start", "period_end", name="uq_kpi_rollup"),
    )

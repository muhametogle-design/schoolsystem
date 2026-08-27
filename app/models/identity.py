"""Global identity & tenancy models: campus, users, managers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from app.models.types import CampusType, SignatureScheme
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

CAMPUS_TYPE_ENUM = (
    "pre_primary",
    "primary",
    "secondary",
    "tvet",
    "tertiary",
    "adult_ed",
)
SIGNATURE_SCHEMES = ("ed25519", "rs256", "es256")


class Campus(Base, TimestampMixin):
    __tablename__ = "campus"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    campus_code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    campus_type: Mapped[str] = mapped_column(CampusType, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False)
    lga: Mapped[str | None] = mapped_column(String)
    postal_address: Mapped[str | None] = mapped_column(Text)
    geo_lat: Mapped[float | None] = mapped_column(Numeric(10, 7))
    geo_lng: Mapped[float | None] = mapped_column(Numeric(10, 7))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AppUser(Base, TimestampMixin):
    __tablename__ = "app_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String, unique=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    campus_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campus.id")
    )
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Manager(Base):
    """NE-MID: global manager identity with the dean's verification key."""

    __tablename__ = "managers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    ne_mid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id"), unique=True, nullable=False
    )
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campus.id"))
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    designation: Mapped[str] = mapped_column(String, nullable=False)
    is_account_holder: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_public_key: Mapped[bytes | None] = mapped_column(BYTEA)
    signature_scheme: Mapped[str] = mapped_column(SignatureScheme, default="ed25519", nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    key_activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    key_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user = relationship("AppUser", lazy="joined")

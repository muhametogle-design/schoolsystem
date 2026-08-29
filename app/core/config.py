"""Application configuration via environment variables (.env supported)."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    app_name: str = "Private School Management & State Compliance Monitoring System"
    app_env: str = "development"

    # --- Database ---
    # Production: postgresql+psycopg2://school:school@db:5432/schoolsystem
    # Demo tier (default): SQLite, so the platform boots with zero infra.
    database_url: str = "sqlite:///./data/schoolsystem.db"

    # --- Auth ---
    jwt_secret_key: str = "dev-only-secret-rotate-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # --- Compliance engine timings ---
    attendance_deadline: str = "12:00"   # mandatory daily roster submission deadline
    alarm_audit_time: str = "15:00"      # 3-hour red alarm audit (3:00 PM)
    platform_timezone: str = "Africa/Nairobi"

    # --- Behaviour flags ---
    auto_seed_demo: bool = True          # seed demo data when the DB comes up empty
    enable_scheduler: bool = True        # run the 15:00 worker loop in-process

    # --- CORS ---
    cors_origins_raw: str = "*"

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()
        if raw == "*" or not raw:
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

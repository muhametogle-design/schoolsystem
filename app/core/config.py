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
    login_rate_limit: int = 5          # failed attempts allowed per window
    login_rate_window_seconds: int = 900

    # --- Identity ---
    app_version: str = "1.0.0"

    # --- Compliance engine timings ---
    attendance_deadline: str = "12:00"   # mandatory daily roster submission deadline
    alarm_audit_time: str = "15:00"      # 3-hour red alarm audit (3:00 PM)
    platform_timezone: str = "Africa/Nairobi"

    # --- Behaviour flags ---
    auto_seed_demo: bool = True          # seed demo data when the DB comes up empty
    enable_scheduler: bool = True        # run the 15:00 worker loop in-process

    # --- Module 4: encrypted midnight backups ---
    backup_time: str = "00:00"           # daily export window (platform timezone)
    backup_dir: str = "data/backups"     # artefacts land here (gitignored)
    backup_retention_days: int = 30      # older completed artefacts are purged
    enable_backup_scheduler: bool = True  # arm the midnight worker loop
    # Passphrase for AES-256-GCM backup encryption. When empty, a key is
    # derived from JWT_SECRET_KEY with a domain-separated KDF (demo tier only —
    # production deployments MUST set a dedicated key).
    backup_encryption_key: str = ""

    # --- Module 5: WebAuthn / biometric hardware ---
    # "auto" resolves the Relying Party ID and expected origin from the
    # request host at runtime (localhost + preview hosts work unmodified).
    # Pin them (e.g. WEBAUTHN_RP_ID=school.example, WEBAUTHN_EXPECTED_ORIGINS=
    # "https://school.example") for production.
    webauthn_rp_id: str = "auto"
    webauthn_expected_origins_raw: str = "auto"

    # --- Session cookie (fallback when the Authorization header is stripped) ---
    # Normal same-site deployments want "lax". Embedded/preview contexts
    # (cross-site iframes) need "none", which browsers only honour with Secure.
    cookie_samesite: str = "lax"        # lax | strict | none
    cookie_secure: str = "auto"         # auto | true | false

    # --- CORS ---
    cors_origins_raw: str = "*"

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()
        if raw == "*" or not raw:
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def cookie_samesite_value(self) -> str:
        """Normalised SameSite value, falling back to 'lax' on anything invalid."""
        value = (self.cookie_samesite or "lax").strip().lower()
        return value if value in {"lax", "strict", "none"} else "lax"

    @property
    def webauthn_expected_origins(self) -> list[str]:
        raw = (self.webauthn_expected_origins_raw or "auto").strip()
        if raw.lower() == "auto" or not raw:
            return ["auto"]
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]

    def resolve_cookie_secure(self, request_scheme: str) -> bool:
        """Resolve the Secure flag.

        'auto' derives it from the request scheme — but behind a TLS-terminating
        proxy the app sees plain http, so operators can force it with
        COOKIE_SECURE=true. SameSite=None always forces Secure (browsers reject
        SameSite=None cookies without it).
        """
        if self.cookie_samesite_value == "none":
            return True
        mode = (self.cookie_secure or "auto").strip().lower()
        if mode == "true":
            return True
        if mode == "false":
            return False
        return request_scheme == "https"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

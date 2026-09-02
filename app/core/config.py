"""Application configuration via environment variables (.env supported)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
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
    # Every field accepts both the canonical JWT_* env name and the common
    # bare name (SECRET_KEY / ALGORITHM), so a mis-named .env never causes a
    # silent fallback to a different signing key between processes.
    jwt_secret_key: str = Field(
        default="dev-only-secret-rotate-me-in-production",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY", "jwt_secret_key"),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "ALGORITHM", "jwt_algorithm"),
    )
    access_token_expire_minutes: int = Field(
        default=480,
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES", "access_token_expire_minutes"),
    )
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

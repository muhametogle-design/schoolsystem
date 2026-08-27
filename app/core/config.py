"""Environment-backed application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "NE-EMIS"
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # Database
    database_url: str = Field(
        default="postgresql+psycopg2://neemis:neemis@localhost:5432/neemis"
    )

    # Authentication / JWT
    # Use HS256 for local development; set RS256 + certificate paths in prod.
    jwt_algorithm: str = Field(default="HS256")
    jwt_public_key_path: Path = Field(default=Path("./certs/jwt-public.pem"))
    jwt_private_key_path: Path = Field(default=Path("./certs/jwt-private.pem"))
    access_token_expire_minutes: int = Field(default=30)
    jwt_secret_key: str = Field(default="dev-only-secret-change-me")

    # CORS
    allowed_origins: str = Field(default="http://localhost:3000,http://localhost:8000")

    # Record locking
    lock_algorithm: str = Field(default="Ed25519")
    lock_key_version: int = Field(default=1)
    state_unlock_roles: str = Field(default="state_admin,system")

    # Aggregation
    aggregation_batch_limit: int = Field(default=10_000)
    aggregation_timezone: str = Field(default="Africa/Lagos")

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def state_unlock_roles_parsed(self) -> List[str]:
        return [r.strip() for r in self.state_unlock_roles.split(",") if r.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

"""Typed application settings loaded from environment variables.

A single ``Settings`` instance is cached via :func:`get_settings` and injected
into FastAPI dependencies. Never read ``os.environ`` directly elsewhere in the
codebase — go through this module so configuration stays type-checked and
documented.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration.

    All fields are populated from environment variables (or a ``.env`` file when
    running locally). Production deployments inject values via Docker / TrueNAS
    secrets; defaults here are safe-but-non-functional placeholders so that the
    process fails fast if a required value is missing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RENO_",
        extra="ignore",
    )

    environment: Literal["development", "staging", "production", "test"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Networking
    api_prefix: str = "/api/v1"
    cors_allow_origins: list[str] = Field(default_factory=list)
    trusted_proxy_ips: list[str] = Field(default_factory=list)

    # Persistence — overridden in docker-compose / .env
    database_url: str = "postgresql+asyncpg://reno:reno@localhost:5432/reno"

    # Auth / crypto
    jwt_secret: SecretStr = SecretStr("change-me-please-this-is-not-a-real-secret")
    jwt_algorithm: Literal["HS256", "HS512"] = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14

    # Uploads
    uploads_dir: str = "/data/uploads"
    upload_max_bytes: int = 25 * 1024 * 1024  # 25 MiB

    # SMTP (used by invitations / password reset / reminders)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "reno-budget@localhost"

    # Worker (Phase 9) — nightly backups + weekly digest emails.
    # ``backups_dir`` is the directory pg_dump writes into. Cron expressions
    # follow APScheduler's CronTrigger.from_crontab() syntax. Retention is
    # measured in finished daily files / finished monthly files.
    backups_dir: str = "./backups"
    worker_backup_cron: str = "30 2 * * *"
    worker_digest_cron: str = "0 7 * * MON"
    worker_backup_retention_daily: int = 30
    worker_backup_retention_monthly: int = 12
    # App-base-URL embedded in digest emails (link to the web UI).
    app_base_url: str = "http://localhost:8080"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached :class:`Settings` instance.

    Cached so importing this function is cheap; the cache is cleared in tests
    via ``get_settings.cache_clear()`` when overriding environment variables.
    """
    return Settings()

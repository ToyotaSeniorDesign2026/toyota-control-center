from __future__ import annotations

from dataclasses import dataclass
import os


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Toyota Control Center API")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    auth_scheme: str = os.getenv("AUTH_SCHEME", "Bearer")

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/control_center",
    )
    db_echo: bool = _as_bool(os.getenv("DB_ECHO"), default=False)

    db_ssl_mode: str = os.getenv("DB_SSL_MODE", "local")
    db_pool_size: int = _as_int(os.getenv("DB_POOL_SIZE"), default=10)
    db_max_overflow: int = _as_int(os.getenv("DB_MAX_OVERFLOW"), default=20)
    db_pool_recycle: int = _as_int(os.getenv("DB_POOL_RECYCLE"), default=1800)
    db_pool_pre_ping: bool = _as_bool(os.getenv("DB_POOL_PRE_PING"), default=True)

    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")


settings = Settings()

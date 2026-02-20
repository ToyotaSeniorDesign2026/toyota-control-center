from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.base import Base


def _build_engine_kwargs() -> dict:
    kwargs = {
        "echo": settings.db_echo,
        "future": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_recycle": settings.db_pool_recycle,
        "pool_pre_ping": settings.db_pool_pre_ping,
    }

    # For PostgreSQL/RDS, pass sslmode through psycopg connection args.
    # Keep local/dev simple by default with DB_SSL_MODE=local.
    if settings.database_url.startswith("postgresql") and settings.db_ssl_mode.lower() != "local":
        kwargs["connect_args"] = {"sslmode": settings.db_ssl_mode}

    return kwargs


engine = create_engine(settings.database_url, **_build_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Convenience for local bootstrapping; Alembic is the source of truth for schema migrations.
    Base.metadata.create_all(bind=engine)

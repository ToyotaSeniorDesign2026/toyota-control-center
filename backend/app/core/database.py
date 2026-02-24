from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.models.user import User
from app.core.db import now_iso


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


_SEEDED = False


def _seed_default_users(db: Session) -> None:
    global _SEEDED
    if _SEEDED:
        return

    existing = db.query(User).count()
    if existing > 0:
        _SEEDED = True
        return

    ts = now_iso()
    db.add_all(
        [
            User(
                id="u_root",
                email="root@toyota.dev",
                name="Root Admin",
                role="root",
                domain="global",
                is_active=True,
                created_at=ts,
            ),
            User(
                id="u_collections_admin",
                email="collections.admin@toyota.dev",
                name="Collections Admin",
                role="domain_admin",
                domain="collections",
                is_active=True,
                created_at=ts,
            ),
            User(
                id="u_analyst",
                email="analyst@toyota.dev",
                name="Analyst User",
                role="user",
                domain="collections",
                is_active=True,
                created_at=ts,
            ),
        ]
    )
    db.commit()
    _SEEDED = True


def get_db_session():
    db = SessionLocal()
    try:
        _seed_default_users(db)
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Convenience for local bootstrapping; Alembic is the source of truth for schema migrations.
    Base.metadata.create_all(bind=engine)

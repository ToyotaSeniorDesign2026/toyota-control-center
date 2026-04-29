from __future__ import annotations

from datetime import datetime
import secrets
import subprocess
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
                first_name="Root",
                last_name="Admin",
                role="root",
                domain="global",
                is_active=True,
                created_at=ts,
                avatar_type="color",
                selected_color="bg-red-500",
                mfa_enabled=True,
                approval_authority=True,
                allowed_environments="dev,staging,prod",
                password_last_changed=datetime.now(),
                access_token=f"cc_root_{secrets.token_hex(16)}",
                cli_token=f"cc_cli_root_{secrets.token_hex(16)}",
                theme="Light",
                notifications="All",
                timezone="UTC-8 (Pacific)",
                job_title="System Administrator",
                department="IT",
                team="DevOps",
                manager=None,
                employee_id="EMP001",
            ),
            User(
                id="u_collections_admin",
                email="collections.admin@toyota.dev",
                name="Collections Admin",
                first_name="Collections",
                last_name="Admin",
                role="domain_admin",
                domain="collections",
                is_active=True,
                created_at=ts,
                avatar_type="color",
                selected_color="bg-purple-500",
                mfa_enabled=True,
                approval_authority=True,
                allowed_environments="dev,staging,prod",
                password_last_changed=datetime.now(),
                access_token=f"cc_admin_{secrets.token_hex(16)}",
                cli_token=f"cc_cli_admin_{secrets.token_hex(16)}",
                theme="Light",
                notifications="Important",
                timezone="UTC-8 (Pacific)",
                job_title="Collections Manager",
                department="Collections",
                team="Management",
                manager="Root Admin",
                employee_id="EMP002",
            ),
            User(
                id="u_analyst",
                email="analyst@toyota.dev",
                name="Analyst User",
                first_name="Analyst",
                last_name="User",
                role="user",
                domain="collections",
                is_active=True,
                created_at=ts,
                avatar_type="color",
                selected_color="bg-blue-500",
                mfa_enabled=True,
                approval_authority=False,
                allowed_environments="dev,staging",
                password_last_changed=datetime.now(),
                access_token=f"cc_user_{secrets.token_hex(16)}",
                cli_token=f"cc_cli_user_{secrets.token_hex(16)}",
                theme="Light",
                notifications="Important",
                timezone="UTC-8 (Pacific)",
                job_title="Data Analyst",
                department="Collections",
                team="Analytics",
                manager="Collections Admin",
                employee_id="EMP003",
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
    # Run Alembic migrations to ensure schema is up-to-date
    try:
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd="/app",
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Migration warning: {e.stderr.decode() if e.stderr else str(e)}")
    except FileNotFoundError:
        # Alembic not in PATH, fall back to metadata.create_all
        print("Alembic not found, falling back to metadata.create_all()")
        Base.metadata.create_all(bind=engine)
    
    # Seed default users on startup
    db = SessionLocal()
    try:
        _seed_default_users(db)
    finally:
        db.close()

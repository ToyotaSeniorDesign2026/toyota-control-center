from __future__ import annotations

<<<<<<< HEAD
from datetime import datetime, timedelta, timezone
import secrets
import subprocess
=======
>>>>>>> polishing-agent-chat
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.models.user import User
<<<<<<< HEAD
from app.models.job import Job
from app.models.run import Run
from app.core.db import now_iso, new_id
=======
from app.core.db import now_iso
>>>>>>> polishing-agent-chat


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
<<<<<<< HEAD
    
    # Demo users to seed
    demo_users = [
        # Root admin
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
        # Department admin (Collections)
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
        # Analyst team members (all in Collections department, domain="collections")
        User(
            id="u_analyst_1",
            email="sarah.chen@toyota.dev",
            name="Sarah Chen",
            first_name="Sarah",
            last_name="Chen",
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
            job_title="Senior Data Analyst",
            department="Collections",
            team="Analytics",
            manager="Collections Admin",
            employee_id="EMP003",
        ),
        User(
            id="u_analyst_2",
            email="michael.johnson@toyota.dev",
            name="Michael Johnson",
            first_name="Michael",
            last_name="Johnson",
            role="user",
            domain="collections",
            is_active=True,
            created_at=ts,
            avatar_type="color",
            selected_color="bg-green-500",
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
            employee_id="EMP004",
        ),
        User(
            id="u_analyst_3",
            email="jane.smith@toyota.dev",
            name="Jane Smith",
            first_name="Jane",
            last_name="Smith",
            role="user",
            domain="collections",
            is_active=True,
            created_at=ts,
            avatar_type="color",
            selected_color="bg-pink-500",
            mfa_enabled=True,
            approval_authority=False,
            allowed_environments="dev,staging",
            password_last_changed=datetime.now(),
            access_token=f"cc_user_{secrets.token_hex(16)}",
            cli_token=f"cc_cli_user_{secrets.token_hex(16)}",
            theme="Light",
            notifications="Important",
            timezone="UTC-8 (Pacific)",
            job_title="Analytics Engineer",
            department="Collections",
            team="Analytics",
            manager="Collections Admin",
            employee_id="EMP005",
        ),
        User(
            id="u_analyst_4",
            email="robert.davis@toyota.dev",
            name="Robert Davis",
            first_name="Robert",
            last_name="Davis",
            role="user",
            domain="collections",
            is_active=True,
            created_at=ts,
            avatar_type="color",
            selected_color="bg-yellow-500",
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
            team="Collections Operations",
            manager="Collections Admin",
            employee_id="EMP006",
        ),
        User(
            id="u_analyst_5",
            email="emily.wilson@toyota.dev",
            name="Emily Wilson",
            first_name="Emily",
            last_name="Wilson",
            role="user",
            domain="collections",
            is_active=True,
            created_at=ts,
            avatar_type="color",
            selected_color="bg-indigo-500",
            mfa_enabled=True,
            approval_authority=False,
            allowed_environments="dev,staging",
            password_last_changed=datetime.now(),
            access_token=f"cc_user_{secrets.token_hex(16)}",
            cli_token=f"cc_cli_user_{secrets.token_hex(16)}",
            theme="Light",
            notifications="Important",
            timezone="UTC-8 (Pacific)",
            job_title="Business Analyst",
            department="Collections",
            team="Collections Operations",
            manager="Collections Admin",
            employee_id="EMP007",
        ),
    ]
    
    db.add_all(demo_users)
=======
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
>>>>>>> polishing-agent-chat
    db.commit()
    _SEEDED = True


<<<<<<< HEAD
def _seed_demo_jobs(db: Session) -> None:
    """Seed demo jobs and runs for all analyst users in the Collections department."""
    # Check if demo jobs already exist
    existing_jobs = db.query(Job).count()
    if existing_jobs > 0:
        return

    # Get all users for seeding
    analyst_users = db.query(User).filter(
        User.role == "user",
        User.domain == "collections"
    ).all()
    
    if not analyst_users:
        return

    ts = now_iso()
    now = datetime.now(timezone.utc)

    # Job templates for different types - each user gets 2-3 of these
    job_templates = [
        {
            "name": "Daily Data Validation",
            "type": "sql_query",
            "connector": "sql_mcp",
            "data_sensitivity": "high",
            "config": {
                "query": "SELECT COUNT(*) FROM collections WHERE status = 'pending'",
                "target": "collections_db",
                "schedule": "daily_08:00"
            }
        },
        {
            "name": "Monthly Receivables Report",
            "type": "excel_report",
            "connector": "excel_mcp",
            "data_sensitivity": "high",
            "config": {
                "template": "receivables_template.xlsx",
                "output": "s3://reports/receivables/",
                "schedule": "monthly_first_monday"
            }
        },
        {
            "name": "Airflow ETL Pipeline",
            "type": "airflow_dag",
            "connector": "airflow_mcp",
            "data_sensitivity": "medium",
            "config": {
                "dag_id": "collections_etl_pipeline",
                "schedule": "daily_midnight",
                "retries": 2
            }
        },
        {
            "name": "Executive Dashboard",
            "type": "powerpoint_presentation",
            "connector": "powerpoint_mcp",
            "data_sensitivity": "high",
            "config": {
                "template": "executive_dashboard.pptx",
                "sections": ["summary", "metrics", "trends"],
                "schedule": "weekly_friday"
            }
        },
        {
            "name": "Invoice Reconciliation",
            "type": "data_reconciliation",
            "connector": "sql_mcp",
            "data_sensitivity": "high",
            "config": {
                "compare_tables": ["invoices", "ar_ledger"],
                "tolerance": 0.01,
                "schedule": "daily_10:00"
            }
        },
        {
            "name": "Weekly Analytics Summary",
            "type": "sql_query",
            "connector": "sql_mcp",
            "data_sensitivity": "medium",
            "config": {
                "query": "SELECT week, total_collections FROM weekly_summary",
                "target": "analytics_db"
            }
        },
    ]

    # Seed jobs and runs for each user
    for user_idx, user in enumerate(analyst_users):
        # Each user gets 2-3 jobs from templates
        num_jobs = 2 + (user_idx % 2)  # Alternates between 2 and 3 jobs per user
        
        for job_template_idx in range(num_jobs):
            job_template = job_templates[job_template_idx % len(job_templates)]
            
            job_id = new_id("job")
            job = Job(
                id=job_id,
                name=job_template["name"],
                type=job_template["type"],
                connector=job_template["connector"],
                kind="runtime",
                owner_id=user.id,
                owner_domain=user.domain,
                environment="dev",
                status="active",
                data_sensitivity=job_template["data_sensitivity"],
                config=job_template["config"],
                tags=["demo", "collections"],
                created_at=ts,
                updated_at=ts,
            )
            db.add(job)

            # Create runs for this job with realistic patterns
            # Create varied run patterns: some healthy, some with issues
            if user_idx == 2 and job_template_idx == 1:  # Jane Smith's Monthly Receivables - with failure
                run_patterns = [
                    ("completed", "low", 20, (now - timedelta(days=7))),
                    ("completed", "low", 25, (now - timedelta(days=6))),
                    ("failed", "high", 75, (now - timedelta(days=4))),  # Recent failure
                    ("completed", "medium", 50, (now - timedelta(days=3))),  # Recovery
                    ("completed", "low", 22, (now - timedelta(hours=2))),
                ]
            elif user_idx == 3 and job_template_idx == 0:  # Michael's Validation with medium risk
                run_patterns = [
                    ("completed", "low", 25, (now - timedelta(days=5))),
                    ("completed", "medium", 55, (now - timedelta(days=3))),
                    ("completed", "medium", 60, (now - timedelta(days=2))),  # Higher risk
                    ("completed", "medium", 52, (now - timedelta(hours=14))),
                    ("completed", "low", 28, (now - timedelta(minutes=45))),
                ]
            elif user_idx == 0 and job_template_idx == 2:  # Sarah's Airflow with high risk
                run_patterns = [
                    ("completed", "low", 30, (now - timedelta(days=6))),
                    ("completed", "medium", 65, (now - timedelta(days=4))),
                    ("failed", "high", 82, (now - timedelta(days=2))),  # Recent high-risk failure
                    ("completed", "high", 70, (now - timedelta(hours=20))),
                    ("completed", "medium", 55, (now - timedelta(minutes=10))),
                ]
            else:  # Default: all healthy runs
                run_patterns = [
                    ("completed", "low", 18 + user_idx, (now - timedelta(days=6))),
                    ("completed", "low", 20 + user_idx, (now - timedelta(days=4))),
                    ("completed", "low", 22 + user_idx, (now - timedelta(days=2))),
                    ("completed", "low", 19 + user_idx, (now - timedelta(hours=4))),
                    ("completed", "low", 17 + user_idx, (now - timedelta(minutes=5))),
                ]

            for run_idx, (status, risk_level, risk_score, run_time) in enumerate(run_patterns):
                run_id = new_id("run")
                run_ts = run_time.isoformat()
                
                error = None
                if status == "failed":
                    if user_idx == 2:
                        error = "Database connection timeout after 30 seconds"
                    elif user_idx == 3:
                        error = "API rate limit exceeded"
                    elif user_idx == 0:
                        error = "Insufficient memory for ETL operation"
                
                run = Run(
                    id=run_id,
                    job_id=job_id,
                    requested_by=user.id,
                    domain=user.domain,
                    action="execute",
                    target_environment="dev",
                    status=status,
                    risk_level=risk_level,
                    risk_score=risk_score,
                    requires_approval=risk_score >= 70,
                    error=error,
                    created_at=run_ts,
                    updated_at=run_ts,
                )
                db.add(run)

    db.commit()



=======
>>>>>>> polishing-agent-chat
def get_db_session():
    db = SessionLocal()
    try:
        _seed_default_users(db)
        yield db
    finally:
        db.close()


def init_db() -> None:
<<<<<<< HEAD
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
        _seed_demo_jobs(db)
    finally:
        db.close()
=======
    # Convenience for local bootstrapping; Alembic is the source of truth for schema migrations.
    Base.metadata.create_all(bind=engine)
>>>>>>> polishing-agent-chat

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
import subprocess
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.models.user import User
from app.models.job import Job
from app.models.run import Run
from app.core.db import now_iso, new_id


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
        # Generic analyst account separate from realistic personas above for testing and demos
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
            selected_color="bg-cyan-500",
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
            employee_id="EMP008",
        ),
    ]
    
    db.add_all(demo_users)
    db.commit()
    _SEEDED = True


def _seed_demo_jobs(db: Session) -> None:
    """Seed demo jobs and runs for all analyst users in the Collections department.

    Existing demo jobs are identified by the "demo" tag attached at create time.
    Set ``SEED_DEMO_JOBS=replace`` to wipe demo jobs and reseed without dropping
    the Postgres volume. ``SEED_DEMO_JOBS=force`` adds another pass on top of
    whatever exists.
    """
    import os
    seed_mode = os.getenv("SEED_DEMO_JOBS", "auto").lower()

    # Filter in Python — Job.tags is plain JSON (not JSONB) so SQLAlchemy's
    # .contains() doesn't reliably translate to a working SQL operator.
    all_jobs = db.query(Job).all()
    existing_demo = [
        j for j in all_jobs
        if isinstance(j.tags, list) and "demo" in j.tags
    ]

    if seed_mode == "replace" and existing_demo:
        demo_ids = {j.id for j in existing_demo}
        for run in db.query(Run).filter(Run.job_id.in_(demo_ids)).all():
            db.delete(run)
        for job in existing_demo:
            db.delete(job)
        db.commit()
    elif seed_mode != "force" and existing_demo:
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

    # Job templates aligned with KNOWN_CONTRACTS (sql, mcp, airflow_python).
    # Connector names match real MCP servers in registry.json so the v2 path
    # can dispatch them without translation. Each user gets a rotating slice.
    sql_db_path = "/app/mcp_servers/sql-mcp-server/test.db"

    job_templates = [
        # ── SQL contract → MCP_TOOL → sql-mcp ───────────────────────────────
        {
            "name": "Delinquency Risk Snapshot",
            "type": "sql",
            "connector": "sql-mcp",
            "data_sensitivity": "high",
            "config": {
                "db_driver": "sqlite",
                "database": sql_db_path,
                "query": "SELECT COUNT(*) AS total FROM delinquency_risk",
                "schedule": "daily_08:00",
            },
        },
        {
            "name": "Recent Defaults Sample",
            "type": "sql",
            "connector": "sql-mcp",
            "data_sensitivity": "high",
            "config": {
                "db_driver": "sqlite",
                "database": sql_db_path,
                "query": "SELECT * FROM delinquency_risk LIMIT 25",
            },
        },
        {
            "name": "SQLite Schema Inspect",
            "type": "sql",
            "connector": "sql-mcp",
            "data_sensitivity": "low",
            "config": {
                "db_driver": "sqlite",
                "database": sql_db_path,
                "query": "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
            },
        },

        # ── MCP Agent contract → MCP_AGENT → various MCP servers ────────────
        {
            "name": "Daily Research Digest",
            "type": "mcp",
            "connector": "arxiv-research",
            "data_sensitivity": "low",
            "config": {
                "prompt": "Search arxiv for one recent paper about LLM tool use and summarize its abstract in 3 sentences.",
                "schedule": "daily_07:00",
            },
        },
        {
            "name": "FastMCP Docs Lookup",
            "type": "mcp",
            "connector": "fastmcp-docs",
            "data_sensitivity": "low",
            "config": {
                "prompt": "Find the FastMCP documentation page about defining tools and quote the example.",
            },
        },
        {
            "name": "Web Page Summary",
            "type": "mcp",
            "connector": "fetch",
            "data_sensitivity": "low",
            "config": {
                "prompt": "Fetch https://en.wikipedia.org/wiki/Toyota and summarize the founding history in 5 bullet points.",
            },
        },
        {
            "name": "GitHub Repo Activity",
            "type": "mcp",
            "connector": "github",
            "data_sensitivity": "medium",
            "config": {
                "prompt": "List the 5 most recent commits to the configured repository and summarize each.",
            },
        },
        {
            "name": "Vocabulary Helper",
            "type": "mcp",
            "connector": "wordsmith-mcp",
            "data_sensitivity": "low",
            "config": {
                "prompt": "Look up the word 'delinquency' and list synonyms appropriate for a financial context.",
            },
        },
        {
            "name": "Filesystem Inventory",
            "type": "mcp",
            "connector": "filesystem",
            "data_sensitivity": "medium",
            "config": {
                "prompt": "List the files in the allowed sandbox directory and describe what each looks like it does.",
            },
        },
        {
            "name": "Browser Automation Demo",
            "type": "mcp",
            "connector": "playwright",
            "data_sensitivity": "low",
            "config": {
                "prompt": "Open https://example.com, take a snapshot, and tell me the page title.",
            },
        },

        # ── Airflow Python contract → AIRFLOW_PYTHON → subprocess scripts ───
        {
            "name": "Hello Toyota (Airflow)",
            "type": "airflow_python",
            "connector": "hello_world",
            "data_sensitivity": "low",
            "config": {
                "run_mode": "subprocess",
                "script": "hello_world",
                "name": "Toyota",
                "multiplier": 3,
            },
        },
        {
            "name": "Daily Metrics Rollup (Airflow)",
            "type": "airflow_python",
            "connector": "daily_metrics",
            "data_sensitivity": "medium",
            "config": {
                "run_mode": "subprocess",
                "script": "daily_metrics",
                "region": "WEST",
                "schedule": "daily_06:00",
            },
        },
        {
            "name": "Data Validation Check (Airflow)",
            "type": "airflow_python",
            "connector": "data_validation",
            "data_sensitivity": "high",
            "config": {
                "run_mode": "subprocess",
                "script": "data_validation",
                "rows": 5000,
                "schedule": "hourly",
            },
        },
    ]

    # Seed jobs and runs for each user. Each analyst gets 4–6 jobs spread
    # across all three contract types so the dashboard shows variety. The
    # offset shifts which slice of templates each user owns so different
    # users surface different MCP servers / Airflow scripts.
    for user_idx, user in enumerate(analyst_users):
        num_jobs = 4 + (user_idx % 3)  # 4, 5, or 6 jobs per user
        offset = (user_idx * 3) % len(job_templates)

        for slot_idx in range(num_jobs):
            template_idx = (offset + slot_idx) % len(job_templates)
            job_template = job_templates[template_idx]
            job_template_idx = template_idx  # legacy var name still used below
            
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
        _seed_demo_jobs(db)
    finally:
        db.close()

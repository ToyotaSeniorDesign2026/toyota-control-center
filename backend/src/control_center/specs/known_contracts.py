from __future__ import annotations

"""Built-in JobTypeContract definitions.

Single source of truth for what each shipped job type looks like:
field schemas, executor wiring, surface requirements, governance defaults.

Currently shipped:
  - sql            → MCP_TOOL    (deterministic execute_sql via sql-mcp)
  - mcp            → MCP_AGENT   (prompt-driven agent loop)
  - airflow_python → AIRFLOW_PYTHON (subprocess-mode Airflow-style task)
"""

from .job_type import (
    ExecutionRequirement,
    ExecutorType,
    FieldSpec,
    FieldType,
    GovernancePolicy,
    InputSchema,
    InteractionSurfaceType,
    JobTypeContract,
    RunFeatures,
)


# ── SQL: deterministic execute_sql call against sql-mcp ──────────────────────

SQL_CONTRACT = JobTypeContract(
    type="sql",
    display_name="SQL Database",
    description="Execute SQL queries against PostgreSQL, SQLite, or Snowflake.",
    supported_actions=["activate", "pause", "archive"],
    deterministic=True,
    executor_type=ExecutorType.MCP_TOOL,
    executor="execute_sql",
    requires=[
        ExecutionRequirement(
            surface_type=InteractionSurfaceType.MCP_SERVER,
            names=["sql-mcp"],
            required_tools=["execute_sql"],
        ),
    ],
    features=RunFeatures(
        supports_retry=True,
        supports_cancel=True,
        supports_schedule=True,
        supports_heartbeat=False,
        max_runtime_seconds=120,
    ),
    policy=GovernancePolicy(),
    source="system",
    config=InputSchema(
        required=["query"],
        optional=["db_driver", "database", "schedule", "timezone"],
        fields={
            "query": FieldSpec(
                name="query",
                type=FieldType.STRING,
                description="SQL statement to execute. Plain English is also accepted and will be converted.",
                placeholder="SELECT * FROM users WHERE active = true",
            ),
            "db_driver": FieldSpec(
                name="db_driver",
                type=FieldType.STRING,
                description="Database driver. Determines how the connection is made.",
                enum=["sqlite", "postgresql", "snowflake"],
                default="postgresql",
            ),
            "database": FieldSpec(
                name="database",
                type=FieldType.STRING,
                description="Database name (PostgreSQL/Snowflake) or absolute file path (SQLite).",
                placeholder="my_database",
            ),
            "schedule": FieldSpec(
                name="schedule",
                type=FieldType.STRING,
                format="cron",
                description="Cron expression for recurring runs.",
                placeholder="0 9 * * 1-5",
            ),
            "timezone": FieldSpec(
                name="timezone",
                type=FieldType.STRING,
                description="IANA timezone for cron evaluation.",
                placeholder="America/New_York",
                default="UTC",
            ),
        },
    ),
    params=InputSchema(
        required=[],
        optional=["host", "port", "username", "password", "query"],
        fields={
            "host": FieldSpec(name="host", type=FieldType.STRING, description="Database server hostname.", placeholder="db.example.com"),
            "port": FieldSpec(name="port", type=FieldType.INTEGER, description="Database server port.", default=5432),
            "username": FieldSpec(name="username", type=FieldType.STRING, description="Database username."),
            "password": FieldSpec(
                name="password",
                type=FieldType.STRING,
                format="secret",
                description="Database password. Never stored — passed per run.",
                sensitive=True,
                write_only=True,
                special_storage="ephemeral",
            ),
            "query": FieldSpec(
                name="query",
                type=FieldType.STRING,
                description="Override the saved query for this run only.",
            ),
        },
    ),
)


# ── MCP Agent: prompt-driven, any approved MCP server ────────────────────────

MCP_CONTRACT = JobTypeContract(
    type="mcp",
    display_name="MCP Agent",
    description="Prompt-driven agent against approved MCP connectors.",
    supported_actions=["activate", "pause", "archive"],
    deterministic=False,
    executor_type=ExecutorType.MCP_AGENT,
    executor="default",
    requires=[
        ExecutionRequirement(
            surface_type=InteractionSurfaceType.MCP_SERVER,
            # Empty names = agent picks at runtime via auto-selection.
            names=[],
        ),
    ],
    features=RunFeatures(
        supports_retry=True,
        supports_cancel=True,
        supports_schedule=False,
        supports_heartbeat=False,
        max_runtime_seconds=300,
    ),
    policy=GovernancePolicy(),
    source="system",
    config=InputSchema(
        required=[],
        optional=["prompt", "description", "schedule", "timezone"],
        fields={
            "prompt": FieldSpec(
                name="prompt",
                type=FieldType.STRING,
                description="Default prompt sent to the MCP agent on each run.",
                placeholder="Summarize the recent activity in...",
            ),
            "description": FieldSpec(
                name="description",
                type=FieldType.STRING,
                description="Human-readable description of what this agent does.",
            ),
            "schedule": FieldSpec(
                name="schedule",
                type=FieldType.STRING,
                format="cron",
                description="Cron expression for recurring runs.",
                placeholder="0 9 * * 1-5",
            ),
            "timezone": FieldSpec(
                name="timezone",
                type=FieldType.STRING,
                description="IANA timezone for schedule evaluation.",
                default="UTC",
            ),
        },
    ),
    params=InputSchema(),
)


# ── Airflow Python: run a Python file as a DAG/task (subprocess mode) ───────

AIRFLOW_PYTHON_CONTRACT = JobTypeContract(
    type="airflow_python",
    display_name="Airflow Python Task",
    description=(
        "Run a Python file as an Airflow-style task. In subprocess mode the "
        "executor invokes `python <script> --params <json>` directly — no "
        "Airflow scheduler needed for development. Use trigger_dag mode in "
        "production to fire a real DAG via Airflow REST."
    ),
    supported_actions=["activate", "pause", "archive"],
    deterministic=True,
    executor_type=ExecutorType.AIRFLOW_PYTHON,
    # The `executor` field names the script identifier. The AirflowPythonExecutor
    # resolves it to /app/scripts/airflow/<executor>.py inside the container
    # (override AIRFLOW_SCRIPT_ROOT to change this base).
    executor="hello_world",
    requires=[
        ExecutionRequirement(
            surface_type=InteractionSurfaceType.PYTHON_RUNTIME,  # Runs in-process subprocess.
            names=[],
        ),
    ],
    features=RunFeatures(
        supports_retry=True,
        supports_cancel=True,
        supports_schedule=True,
        supports_heartbeat=False,
        max_runtime_seconds=300,
    ),
    policy=GovernancePolicy(),
    source="system",
    config=InputSchema(
        required=[],
        optional=["run_mode", "script", "airflow_url", "airflow_token"],
        fields={
            "run_mode": FieldSpec(
                name="run_mode",
                type=FieldType.STRING,
                enum=["subprocess", "trigger_dag"],
                default="subprocess",
                description=(
                    "subprocess: run the Python file directly. "
                    "trigger_dag: hit Airflow REST to start a real DAG run."
                ),
            ),
            "script": FieldSpec(
                name="script",
                type=FieldType.STRING,
                description=(
                    "Override the script identifier set on the contract's "
                    "executor field. Bare name → /app/scripts/airflow/<name>.py."
                ),
                placeholder="hello_world",
            ),
            "airflow_url": FieldSpec(
                name="airflow_url",
                type=FieldType.STRING,
                format="uri",
                description="Base URL of the Airflow API (trigger_dag mode only).",
                placeholder="https://airflow.internal/api/v1",
            ),
            "airflow_token": FieldSpec(
                name="airflow_token",
                type=FieldType.STRING,
                format="secret",
                description="Bearer token for the Airflow API (trigger_dag mode only).",
                sensitive=True,
                write_only=True,
                special_storage="session",
            ),
        },
    ),
    # All run params are forwarded to the script as JSON via --params.
    # No fixed schema — anything the script needs is fair game.
    params=InputSchema(
        required=[],
        optional=["name", "multiplier"],
        fields={
            "name": FieldSpec(
                name="name",
                type=FieldType.STRING,
                description="Sample param consumed by the bundled hello_world.py demo task.",
                placeholder="world",
            ),
            "multiplier": FieldSpec(
                name="multiplier",
                type=FieldType.INTEGER,
                description="How many times to repeat the greeting (hello_world demo).",
                default=1,
            ),
        },
    ),
)


KNOWN_CONTRACTS: dict[str, JobTypeContract] = {
    "sql": SQL_CONTRACT,
    "mcp": MCP_CONTRACT,
    "airflow_python": AIRFLOW_PYTHON_CONTRACT,
}

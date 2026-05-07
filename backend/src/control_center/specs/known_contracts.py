from __future__ import annotations

"""Built-in JobTypeContract definitions.

Single source of truth for what each shipped job type looks like:
field schemas, executor wiring, surface requirements, governance defaults.

For MVP: two contracts (sql, mcp). Add more as new ExecutorType variants
land in the EXECUTOR_REGISTRY.
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


KNOWN_CONTRACTS: dict[str, JobTypeContract] = {
    "sql": SQL_CONTRACT,
    "mcp": MCP_CONTRACT,
}

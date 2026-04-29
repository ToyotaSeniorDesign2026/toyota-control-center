from __future__ import annotations

"""Canonical JobTypeContract definitions for built-in job types.

Each entry is the single source of truth for:
  - which fields belong to job config vs run-time params
  - field types, formats, placeholders, and sensitivity
  - execution wiring (executor, required MCP tools/scopes)
  - governance defaults
  - the form_schema() used by MCP App dynamic UI
"""

from .job_type import (
    ArtifactSpec,
    CapabilityRequirement,
    FieldSpec,
    FieldType,
    GovernancePolicy,
    InputSchema,
    JobTypeContract,
    RunFeatures,
)

SQL_CONTRACT = JobTypeContract(
    type="sql",
    display_name="SQL Database",
    description="Execute SQL queries against PostgreSQL, SQLite, or Snowflake databases.",
    kind="runtime",
    supported_actions=["activate", "pause", "archive"],
    executor="mcp",
    requires=CapabilityRequirement(
        connector_types=["sql-mcp"],
        required_tools=["execute_sql"],
    ),
    features=RunFeatures(
        supports_retry=True,
        supports_cancel=True,
        supports_schedule=True,
        supports_heartbeat=False,
        max_runtime_seconds=120,
    ),
    policy=GovernancePolicy(
        approval_threshold=60,
        approval_required_in=["prod"],
    ),
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
                description="Cron expression for recurring runs. Omit for manual-only jobs.",
                placeholder="0 9 * * 1-5",
            ),
            "timezone": FieldSpec(
                name="timezone",
                type=FieldType.STRING,
                description="IANA timezone used to evaluate the cron schedule.",
                placeholder="America/New_York",
                default="UTC",
            ),
        },
    ),
    params=InputSchema(
        required=[],
        optional=["host", "port", "username", "password", "query"],
        fields={
            "host": FieldSpec(
                name="host",
                type=FieldType.STRING,
                description="Database server hostname.",
                placeholder="db.example.com",
            ),
            "port": FieldSpec(
                name="port",
                type=FieldType.INTEGER,
                description="Database server port.",
                default=5432,
            ),
            "username": FieldSpec(
                name="username",
                type=FieldType.STRING,
                description="Database username.",
            ),
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

REPO_CONNECTION_CONTRACT = JobTypeContract(
    type="repo_connection",
    display_name="GitHub Repository",
    description="Connect a GitHub repository for context-aware read and write workflows.",
    kind="runtime",
    supported_actions=["activate", "pause", "archive"],
    executor="mcp",
    requires=CapabilityRequirement(
        connector_types=["github"],
        required_scopes=["repo"],
    ),
    features=RunFeatures(
        supports_retry=False,
        supports_cancel=False,
        supports_schedule=False,
        supports_heartbeat=False,
        max_runtime_seconds=60,
    ),
    policy=GovernancePolicy(
        approval_threshold=60,
        approval_required_in=["prod"],
    ),
    source="system",
    config=InputSchema(
        required=["repo"],
        optional=["ref", "path", "provider"],
        fields={
            "repo": FieldSpec(
                name="repo",
                type=FieldType.STRING,
                description="GitHub repository in owner/name format.",
                placeholder="acme/data-models",
            ),
            "ref": FieldSpec(
                name="ref",
                type=FieldType.STRING,
                description="Branch, tag, or commit SHA. Defaults to the repository default branch.",
                placeholder="main",
            ),
            "path": FieldSpec(
                name="path",
                type=FieldType.STRING,
                description="Directory within the repository to scope the connection to.",
                placeholder="models/",
            ),
            "provider": FieldSpec(
                name="provider",
                type=FieldType.STRING,
                description="Git provider.",
                enum=["github"],
                default="github",
            ),
        },
    ),
    params=InputSchema(
        required=[],
        optional=["github_token"],
        fields={
            "github_token": FieldSpec(
                name="github_token",
                type=FieldType.STRING,
                format="secret",
                description="Personal access token for private repositories. Never stored.",
                sensitive=True,
                write_only=True,
                special_storage="session",
            ),
        },
    ),
)

MCP_CONTRACT = JobTypeContract(
    type="mcp",
    display_name="MCP Agent",
    description="Prompt-driven agent against any approved MCP connector.",
    kind="runtime",
    supported_actions=["activate", "pause", "archive"],
    executor="mcp",
    requires=CapabilityRequirement(),
    features=RunFeatures(
        supports_retry=True,
        supports_cancel=True,
        supports_schedule=False,
        supports_heartbeat=False,
        max_runtime_seconds=300,
    ),
    policy=GovernancePolicy(
        approval_threshold=60,
        approval_required_in=["prod"],
    ),
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
    "repo_connection": REPO_CONNECTION_CONTRACT,
    "mcp": MCP_CONTRACT,
}

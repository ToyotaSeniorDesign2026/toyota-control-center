"""Slim SQL MCP server.

Three tools — execute_sql, list_tables, test_connection. Connection details
are passed PER CALL via the optional `connection` arg (preferred) and fall
back to SQL_DB_* env vars when not provided.

This is the "reactive" shape: the executor reads job.config (db_driver,
database, host, port, username, password, warehouse) and passes them
directly into each tool call. Env-var fallback exists so the server can
be exercised standalone (CLI, tests) without a job context.

Supported drivers: PostgreSQL (default), SQLite, Snowflake, plus any
SQLAlchemy-compatible driver string.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import quote_plus, urlencode

from sqlalchemy import create_engine, text
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

MAX_ROWS = int(os.environ.get("SQL_MAX_ROWS", "500"))
CONNECT_TIMEOUT = int(os.environ.get("SQL_CONNECT_TIMEOUT", "15"))


def _from_connection_or_env(connection: dict[str, Any] | None, key: str, env_key: str, default: str = "") -> str:
    """Pick a value: per-call connection arg first, env var second, default last."""
    if connection and (val := connection.get(key)) not in (None, ""):
        return str(val).strip()
    env_val = os.environ.get(env_key, default).strip()
    # Treat unexpanded ${...} as unset
    if env_val.startswith("${") and env_val.endswith("}"):
        return default
    return env_val


def _build_url(connection: dict[str, Any] | None) -> tuple[str, str]:
    """Return (sqlalchemy_url, driver). Raises RuntimeError if config incomplete."""
    driver = (
        _from_connection_or_env(connection, "db_driver", "SQL_DB_DRIVER", "postgresql+psycopg")
        .lower()
    )

    if driver == "sqlite":
        database = _from_connection_or_env(connection, "database", "SQL_DB_DATABASE")
        if not database:
            raise RuntimeError("SQLite requires `database` (file path or ':memory:').")
        url = "sqlite://" if database == ":memory:" else f"sqlite:///{database}"
        return url, driver

    host = _from_connection_or_env(connection, "host", "SQL_DB_HOST")
    port = _from_connection_or_env(connection, "port", "SQL_DB_PORT", "5432")
    database = _from_connection_or_env(connection, "database", "SQL_DB_DATABASE")
    username = _from_connection_or_env(connection, "username", "SQL_DB_USERNAME")
    password = _from_connection_or_env(connection, "password", "SQL_DB_PASSWORD")

    missing = [k for k, v in {"host": host, "database": database, "username": username, "password": password}.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing SQL connection fields: {missing}. "
            f"Pass them via the `connection` arg or SQL_DB_* env vars."
        )

    if driver in ("snowflake", "snowflake+snowflake-sqlalchemy"):
        account = re.sub(r"\.snowflakecomputing\.com$", "", host, flags=re.IGNORECASE)
        warehouse = _from_connection_or_env(connection, "warehouse", "SQL_DB_WAREHOUSE")
        qs = ("?" + urlencode({"warehouse": warehouse})) if warehouse else ""
        url = f"snowflake://{quote_plus(username)}:{quote_plus(password)}@{account}/{database}{qs}"
        return url, driver

    url = f"{driver}://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}"
    return url, driver


def _make_engine(connection: dict[str, Any] | None):
    url, driver = _build_url(connection)
    connect_args = {} if driver == "sqlite" else {"connect_timeout": CONNECT_TIMEOUT}
    return create_engine(url, connect_args=connect_args), driver


mcp = FastMCP("sql-mcp-server")


@mcp.tool()
def test_connection(connection: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify that the connection settings can reach the database.

    Args:
        connection: Optional dict with keys db_driver, host, port, database,
                    username, password, warehouse. Falls back to SQL_DB_* env
                    vars when not provided.

    Returns:
        On success: {"ok": true, "driver": "<driver>", "database": "<db>"}
        On failure: {"ok": false, "error": "<message>"}
    """
    try:
        engine, driver = _make_engine(connection)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "ok": True,
            "driver": driver,
            "database": _from_connection_or_env(connection, "database", "SQL_DB_DATABASE"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def list_tables(connection: dict[str, Any] | None = None) -> dict[str, Any]:
    """List user tables in the connected database.

    Returns {"tables": [...], "error": null} or {"tables": [], "error": "<msg>"}.
    """
    try:
        engine, driver = _make_engine(connection)
        if driver == "sqlite":
            q = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        else:
            q = (
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'INFORMATION_SCHEMA') "
                "ORDER BY table_name"
            )
        with engine.connect() as conn:
            result = conn.execute(text(q))
            return {"tables": [row[0] for row in result], "error": None}
    except Exception as exc:
        return {"tables": [], "error": str(exc)}


@mcp.tool()
def execute_sql(query: str, connection: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a SQL statement, returning up to 500 rows when rows are produced.

    Args:
        query: A valid SQL statement.
        connection: Optional per-call connection override (see test_connection).

    Returns dict with: columns, rows, row_count, truncated, error.
    On failure, error contains the message and rows/columns are empty.
    """
    try:
        engine, _ = _make_engine(connection)
        with engine.begin() as conn:
            result = conn.execute(text(query))
            if not result.returns_rows:
                return {
                    "columns": [],
                    "rows": [],
                    "row_count": result.rowcount if result.rowcount is not None else 0,
                    "truncated": False,
                    "error": None,
                }
            columns = list(result.keys())
            rows = result.fetchmany(MAX_ROWS)
            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "row_count": len(rows),
                "truncated": len(rows) == MAX_ROWS,
                "error": None,
            }
    except Exception as exc:
        return {
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "error": str(exc),
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")

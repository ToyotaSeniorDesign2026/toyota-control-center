"""Generic FastMCP SQL server.

Supports PostgreSQL, SQLite, and Snowflake (and any other SQLAlchemy dialect).

Connection configuration (pick one approach):

  PostgreSQL / Snowflake — ADO.NET-style string:
    SQL_CONNECTION_STRING=Host=h;Port=p;Database=d;Username=u;Password=pw

  PostgreSQL / Snowflake — individual vars:
    SQL_DB_DRIVER=postgresql+psycopg   # default
    SQL_DB_HOST, SQL_DB_PORT, SQL_DB_DATABASE, SQL_DB_USERNAME, SQL_DB_PASSWORD

  SQLite — file path:
    SQL_DB_DRIVER=sqlite
    SQL_DB_DATABASE=/path/to/file.db   # or ":memory:"

  Snowflake — individual vars:
    SQL_DB_DRIVER=snowflake
    SQL_DB_HOST=<account>.snowflakecomputing.com
    SQL_DB_DATABASE=<database>/<schema>
    SQL_DB_USERNAME=<user>
    SQL_DB_PASSWORD=<password>
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from sqlalchemy import create_engine, text
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

MAX_ROWS = 500

_ADOINET_RE = re.compile(
    r"Host=(?P<host>[^;]+);Port=(?P<port>[^;]+);Database=(?P<database>[^;]+);"
    r"Username=(?P<username>[^;]+);Password=(?P<password>[^;]+)",
    re.IGNORECASE,
)

_CONNECT_TIMEOUT = int(os.environ.get("SQL_CONNECT_TIMEOUT", "15"))
_QUERY_TIMEOUT = int(os.environ.get("SQL_QUERY_TIMEOUT", "30"))


def _resolved(key: str, default: str = "") -> str:
    """Get env var, treating unexpanded ${...} templates as unset."""
    val = os.environ.get(key, default).strip()
    return default if (val.startswith("${") and val.endswith("}")) else val


def _build_sqlalchemy_url() -> str:
    driver = (_resolved("SQL_DB_DRIVER") or "postgresql+psycopg").lower()

    # SQLite — only needs a file path
    if driver == "sqlite":
        database = _resolved("SQL_DB_DATABASE")
        if not database:
            raise RuntimeError(
                "SQLite requires SQL_DB_DATABASE set to a file path or ':memory:'."
            )
        return f"sqlite:///{database}" if database != ":memory:" else "sqlite://"

    # All other drivers — try ADO.NET string first, then individual vars
    raw = _resolved("SQL_CONNECTION_STRING")
    m = _ADOINET_RE.search(raw)
    if m:
        host = m.group("host")
        port = m.group("port")
        database = m.group("database")
        username = m.group("username")
        password = m.group("password")
    else:
        host = _resolved("SQL_DB_HOST")
        port = _resolved("SQL_DB_PORT", "5432")
        database = _resolved("SQL_DB_DATABASE")
        username = _resolved("SQL_DB_USERNAME")
        password = _resolved("SQL_DB_PASSWORD")

    if not all([host, database, username, password]):
        raise RuntimeError(
            "SQL connection not configured. Set SQL_CONNECTION_STRING or "
            "SQL_DB_HOST / SQL_DB_PORT / SQL_DB_DATABASE / SQL_DB_USERNAME / SQL_DB_PASSWORD."
        )

    # Snowflake uses a different URL shape.
    # The account identifier must not include .snowflakecomputing.com.
    if driver in ("snowflake", "snowflake+snowflake-sqlalchemy"):
        from urllib.parse import quote_plus, urlencode
        account = re.sub(r"\.snowflakecomputing\.com$", "", host, flags=re.IGNORECASE)
        warehouse = _resolved("SQL_DB_WAREHOUSE")
        qs = ("?" + urlencode({"warehouse": warehouse})) if warehouse else ""
        return (
            f"snowflake://"
            f"{quote_plus(username)}:{quote_plus(password)}@{account}/{database}{qs}"
        )

    from urllib.parse import quote_plus
    return f"{driver}://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}"


def _make_engine():
    url = _build_sqlalchemy_url()
    driver = (_resolved("SQL_DB_DRIVER") or "postgresql+psycopg").lower()
    connect_args = {} if driver == "sqlite" else {"connect_timeout": _CONNECT_TIMEOUT}
    return create_engine(url, connect_args=connect_args)


def _list_tables_query() -> str:
    driver = (_resolved("SQL_DB_DRIVER") or "postgresql+psycopg").lower()
    if driver == "sqlite":
        return "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    # Snowflake and PostgreSQL both support information_schema
    return (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'INFORMATION_SCHEMA') "
        "ORDER BY table_name"
    )


mcp = FastMCP("sql-mcp-server")


@mcp.tool()
def test_connection() -> dict[str, Any]:
    """Verify that the current connection settings can reach the database.

    Call this first whenever sql-mcp becomes available (after the user submits
    connection credentials) to confirm the connection works before calling
    list_tables or execute_sql.

    Returns:
        On success: {"ok": true, "driver": "<driver>", "database": "<db>", "host": "<host>"}
        On failure: {"ok": false, "error": "<message>"}
          Common errors:
            "database does not exist"  — wrong database name, ask user to correct it
            "connection refused"       — wrong host/port
            "authentication failed"    — wrong username/password
    """
    try:
        url = _build_sqlalchemy_url()
        driver = (_resolved("SQL_DB_DRIVER") or "postgresql+psycopg").lower()
        connect_args = {} if driver == "sqlite" else {"connect_timeout": _CONNECT_TIMEOUT}
        engine = create_engine(url, connect_args=connect_args)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "ok": True,
            "driver": driver,
            "database": _resolved("SQL_DB_DATABASE"),
            "host": _resolved("SQL_DB_HOST"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def list_tables() -> dict[str, Any]:
    """Return the names of all user tables in the connected database.

    If the connection fails (e.g. wrong database name, bad credentials), returns an
    error dict instead of raising. Tell the user the specific error and ask them to
    correct the connection details — do not retry with the same values.

    Returns {"tables": [...]} on success or {"error": "<message>"} on failure.
    """
    try:
        engine = _make_engine()
        with engine.connect() as conn:
            result = conn.execute(text(_list_tables_query()))
            return {"tables": [row[0] for row in result]}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_table_columns(table_name: str) -> dict[str, Any]:
    """Return column names and data types for a table in the connected database.

    Call this after list_tables to inspect a table's schema before writing a query.

    Args:
        table_name: Exact table name as returned by list_tables.

    Returns {"columns": [{name, type}, ...]} on success or {"error": "<message>"} on failure.
    """
    driver = (_resolved("SQL_DB_DRIVER") or "postgresql+psycopg").lower()
    try:
        engine = _make_engine()
        with engine.connect() as conn:
            if driver == "sqlite":
                result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                columns = [{"name": row[1], "type": row[2]} for row in result]
            else:
                result = conn.execute(
                    text(
                        "SELECT column_name, data_type "
                        "FROM information_schema.columns "
                        "WHERE table_name = :t "
                        "ORDER BY ordinal_position"
                    ),
                    {"t": table_name},
                )
                columns = [{"name": row[0], "type": row[1]} for row in result]
        return {"columns": columns}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def execute_sql(query: str) -> dict[str, Any]:
    """Execute a SQL statement and return up to 500 rows when rows are produced.

    Args:
        query: A valid SQL statement.

    Returns a dict with keys: columns, rows, row_count, truncated, error.
    On failure, error contains the message and rows/columns are empty.
    """
    try:
        engine = _make_engine()
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
            truncated = len(rows) == MAX_ROWS
        return {
            "columns": columns,
            "rows": [list(row) for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
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


@mcp.tool()
def validate_sql_syntax(query: str) -> dict[str, Any]:
    """Check whether a SQL statement is syntactically valid without executing it.

    Uses the database driver's EXPLAIN / query-plan mechanism to parse the query.
    Returns {"valid": true} on success or {"valid": false, "error": "<message>"} on failure.

    Args:
        query: The SQL statement to validate.
    """
    if not query or not query.strip():
        return {"valid": False, "error": "Query is empty."}
    try:
        driver = (_resolved("SQL_DB_DRIVER") or "postgresql+psycopg").lower()
        engine = _make_engine()
        with engine.connect() as conn:
            if driver == "sqlite":
                # SQLite supports EXPLAIN; it raises on syntax errors.
                conn.execute(text(f"EXPLAIN {query}"))
            elif driver in ("snowflake", "snowflake+snowflake-sqlalchemy"):
                # Snowflake supports EXPLAIN USING TABULAR.
                conn.execute(text(f"EXPLAIN USING TABULAR {query}"))
            else:
                # PostgreSQL and MySQL both support EXPLAIN.
                conn.execute(text(f"EXPLAIN {query}"))
        return {"valid": True}
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


if __name__ == "__main__":
    mcp.run(transport="stdio")

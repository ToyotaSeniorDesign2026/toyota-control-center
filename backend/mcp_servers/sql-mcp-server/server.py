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


def _build_sqlalchemy_url() -> str:
    driver = os.environ.get("SQL_DB_DRIVER", "postgresql+psycopg").strip().lower()

    # SQLite — only needs a file path
    if driver == "sqlite":
        database = os.environ.get("SQL_DB_DATABASE", "").strip()
        if not database:
            raise RuntimeError(
                "SQLite requires SQL_DB_DATABASE set to a file path or ':memory:'."
            )
        return f"sqlite:///{database}" if database != ":memory:" else "sqlite://"

    # All other drivers — try ADO.NET string first, then individual vars
    raw = os.environ.get("SQL_CONNECTION_STRING", "")
    m = _ADOINET_RE.search(raw)
    if m:
        host = m.group("host")
        port = m.group("port")
        database = m.group("database")
        username = m.group("username")
        password = m.group("password")
    else:
        host = os.environ.get("SQL_DB_HOST", "")
        port = os.environ.get("SQL_DB_PORT", "5432")
        database = os.environ.get("SQL_DB_DATABASE", "")
        username = os.environ.get("SQL_DB_USERNAME", "")
        password = os.environ.get("SQL_DB_PASSWORD", "")

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
        warehouse = os.environ.get("SQL_DB_WAREHOUSE", "").strip()
        qs = ("?" + urlencode({"warehouse": warehouse})) if warehouse else ""
        return (
            f"snowflake://"
            f"{quote_plus(username)}:{quote_plus(password)}@{account}/{database}{qs}"
        )

    from urllib.parse import quote_plus
    return f"{driver}://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}"


def _make_engine():
    url = _build_sqlalchemy_url()
    driver = os.environ.get("SQL_DB_DRIVER", "postgresql+psycopg").strip().lower()
    connect_args = {} if driver == "sqlite" else {"connect_timeout": _CONNECT_TIMEOUT}
    return create_engine(url, connect_args=connect_args)


def _list_tables_query() -> str:
    driver = os.environ.get("SQL_DB_DRIVER", "postgresql+psycopg").strip().lower()
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
def list_tables() -> list[str]:
    """Return the names of all user tables in the connected database."""
    engine = _make_engine()
    with engine.connect() as conn:
        result = conn.execute(text(_list_tables_query()))
        return [row[0] for row in result]


@mcp.tool()
def execute_query(query: str) -> dict[str, Any]:
    """Execute a SQL statement and return up to 500 rows when rows are produced.

    Args:
        query: A valid SQL statement.
    """
    engine = _make_engine()
    with engine.begin() as conn:
        result = conn.execute(text(query))
        if not result.returns_rows:
            return {
                "columns": [],
                "rows": [],
                "row_count": result.rowcount if result.rowcount is not None else 0,
                "truncated": False,
            }
        columns = list(result.keys())
        rows = result.fetchmany(MAX_ROWS)
        truncated = len(rows) == MAX_ROWS

    return {
        "columns": columns,
        "rows": [list(row) for row in rows],
        "row_count": len(rows),
        "truncated": truncated,
    }


@mcp.tool()
def execute_sql(query: str, connection_id: str | None = None) -> dict[str, Any]:
    """Compatibility alias for Control Center direct-tool SQL execution."""
    return execute_query(query)


if __name__ == "__main__":
    mcp.run(transport="stdio")

"""Generic FastMCP SQL server.

Reads SQL_CONNECTION_STRING from env at startup (ADO.NET format:
  Host=h;Port=p;Database=d;Username=u;Password=pw
or individual SQL_DB_* vars) and exposes execute_query / list_tables tools.
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


def _build_sqlalchemy_url() -> str:
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

    from urllib.parse import quote_plus
    return f"postgresql+psycopg://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}"


mcp = FastMCP("sql-mcp-server")


_CONNECT_TIMEOUT = int(os.environ.get("SQL_CONNECT_TIMEOUT", "15"))
_QUERY_TIMEOUT = int(os.environ.get("SQL_QUERY_TIMEOUT", "30"))


def _make_engine():
    return create_engine(
        _build_sqlalchemy_url(),
        connect_args={"connect_timeout": _CONNECT_TIMEOUT},
    )


@mcp.tool()
def list_tables() -> list[str]:
    """Return the names of all user tables in the connected database."""
    engine = _make_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        )
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

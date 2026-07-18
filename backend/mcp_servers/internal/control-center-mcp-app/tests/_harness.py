"""Shared test machinery for the Control Center Job Designer MCP App suite.

Design notes (these encode the anti-patterns reference in this folder):

* **Mock only the real external boundary.** The single dependency the app
  cannot exercise offline is the Control Center HTTP API, reached through
  ``utils.api_get`` / ``utils.api_post``. Those are the *lowest level* worth
  faking (anti-pattern #3). Everything above them — schema resolution, draft
  state, secret masking, Prefab rendering, MCP wire framing — runs for real
  through an in-memory FastMCP client.

* **Complete fakes.** ``job_out`` / ``connector_out`` mirror the real
  ``app.schemas.job.JobOut`` / ``app.schemas.connector.ConnectorOut`` shapes in
  full, so a tool that reads any field downstream sees a realistic object
  (anti-pattern #4), not a convenient subset.

* **No production test hooks.** All setup/teardown lives here, never on the
  server (anti-pattern #2). Each test builds its own ``build_server()`` so the
  process-global draft state is isolated per test.
"""

from __future__ import annotations

import contextlib
from typing import Any, Callable
from unittest import mock

import httpx

import forms
import server as server_module
import utils
from fastmcp import Client
from fastmcp.client.client import CallToolResult

build_server = server_module.build_server


# ── In-memory MCP client ──────────────────────────────────────────────────────

def mcp_client(srv=None) -> Client:
    """An in-memory FastMCP client speaking the real protocol to a fresh server.

    Usage::

        async with mcp_client() as client:
            tools = await client.list_tools()
    """
    return Client(srv if srv is not None else build_server())


# ── Fake Control Center backend (the only mocked boundary) ────────────────────

class BackendError(httpx.ConnectError):
    """Raised by the fake for unrouted paths — mimics a backend that is down.

    Tools are expected to degrade gracefully (offline fallback) when the API is
    unreachable; raising the real httpx error type exercises that path honestly.
    """


Route = Callable[..., Any] | Any


class FakeBackend:
    """Records API calls and serves configured responses.

    Routes are keyed by exact path (``/jobs``, ``/jobs/abc/runs`` …). A route
    value may be a literal (returned as-is) or a callable taking the request
    payload (``params`` for GET, ``body`` for POST) and returning the response.
    Unrouted paths raise :class:`BackendError` to simulate an unreachable API.
    """

    def __init__(self) -> None:
        self.get_routes: dict[str, Route] = {}
        self.post_routes: dict[str, Route] = {}
        self.calls: list[tuple[str, str, Any]] = []

    # -- configuration --------------------------------------------------------
    def on_get(self, path: str, response: Route) -> "FakeBackend":
        self.get_routes[path] = response
        return self

    def on_post(self, path: str, response: Route) -> "FakeBackend":
        self.post_routes[path] = response
        return self

    # -- request handlers (patched over utils.api_get / utils.api_post) --------
    def api_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append(("GET", path, params))
        if path not in self.get_routes:
            raise BackendError(f"no fake route for GET {path}")
        route = self.get_routes[path]
        return route(params) if callable(route) else route

    def api_post(self, path: str, body: dict[str, Any]) -> Any:
        self.calls.append(("POST", path, body))
        if path not in self.post_routes:
            raise BackendError(f"no fake route for POST {path}")
        route = self.post_routes[path]
        return route(body) if callable(route) else route

    # -- assertions / inspection ----------------------------------------------
    def last_body(self, method: str, path: str) -> Any:
        for m, p, payload in reversed(self.calls):
            if m == method and p == path:
                return payload
        raise AssertionError(f"no recorded {method} {path} call in {self.calls}")

    def called(self, method: str, path: str) -> bool:
        return any(m == method and p == path for m, p, _ in self.calls)


@contextlib.contextmanager
def patched_backend(fake: FakeBackend):
    """Route every backend HTTP call through ``fake`` for the block's duration.

    ``forms`` does ``from utils import api_get`` (a separate binding), so both
    ``utils.api_get`` and ``forms.api_get`` must be patched; ``api_post`` is only
    referenced via ``utils.`` attribute access from ``server``.
    """
    with mock.patch.object(utils, "api_get", fake.api_get), \
         mock.patch.object(utils, "api_post", fake.api_post), \
         mock.patch.object(forms, "api_get", fake.api_get):
        yield fake


# ── Complete response factories (mirror the real Pydantic schemas) ────────────

def job_out(**overrides: Any) -> dict[str, Any]:
    """A full ``app.schemas.job.JobOut`` dict; override any field."""
    base = {
        "id": "job_test_0001",
        "name": "Test Job",
        "kind": "runtime",
        "type": "sql",
        "connector": "sql-mcp",
        "owner_id": "u_test",
        "owner_domain": "platform",
        "environment": "dev",
        "status": "registered",
        "data_sensitivity": "low",
        "config": {},
        "tags": [],
        "risk_score": None,
        "risk_level": None,
        "owner_name": None,
        "last_run_at": None,
        "last_run_status": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def connector_out(**overrides: Any) -> dict[str, Any]:
    """A full ``app.schemas.connector.ConnectorOut`` dict; override any field."""
    base = {
        "id": "conn_test_0001",
        "name": "primary-sql",
        "connector_type": "sql-mcp",
        "owner_id": "u_test",
        "owner_domain": "platform",
        "environment": "dev",
        "status": "active",
        "config": {},
        "is_shared": False,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def run_out(**overrides: Any) -> dict[str, Any]:
    """A full ``app.schemas.run.RunOut`` dict; override any field."""
    base = {
        "id": "run_test_0001",
        "job_id": "job_test_0001",
        "requested_by": "u_test",
        "domain": "platform",
        "action": "run",
        "target_environment": "dev",
        "status": "queued",
        "risk_level": "low",
        "risk_score": 0,
        "requires_approval": False,
        "approval_id": None,
        "connector_run_id": None,
        "error": None,
        "promotion_status": None,
        "git_ref": None,
        "pr_number": None,
        "commit_sha": None,
        "workflow_run_id": None,
        "workflow_url": None,
        "trigger_source": "mcp",
        "execution_backend": None,
        "execution_mode": None,
        "submitted_config_json": None,
        "resolved_job_spec_json": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def connector_list(*items: dict[str, Any]) -> dict[str, Any]:
    """A full ``ConnectorListOut`` envelope around ``items``."""
    return {
        "items": list(items),
        "total": len(items),
        "page": 1,
        "page_size": max(len(items), 1),
        "has_more": False,
    }


# ── Result / metadata accessors ───────────────────────────────────────────────

def structured(result: CallToolResult) -> dict[str, Any]:
    """The tool's structured_content, asserting it exists."""
    assert result.structured_content is not None, "tool returned no structured_content"
    return result.structured_content


def first_text(result: CallToolResult) -> str:
    """Text of the first content block (used for error-message assertions)."""
    assert result.content, "tool returned no content blocks"
    block = result.content[0]
    return getattr(block, "text", "")


def tool_map(tools: list[Any]) -> dict[str, Any]:
    return {t.name: t for t in tools}


def ui_meta(obj: Any) -> dict[str, Any]:
    """The ``_meta.ui`` block for a Tool or Resource (empty dict if absent)."""
    meta = getattr(obj, "meta", None) or {}
    return meta.get("ui") or {}

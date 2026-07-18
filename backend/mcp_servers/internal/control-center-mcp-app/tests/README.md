# Control Center Job Designer — MCP App test suite

End-to-end tests for the Job Designer MCP App (`server.py`), driven through a
real in-memory FastMCP client. Conformance assertions are anchored to the two
specs vendored alongside these tests — `mcp-schema.mdx` (base MCP) and
`mcp-apps.mdx` (the MCP Apps extension) — and follow the rules in
`testing-anti-patterns.md`.

## Running

```bash
# from anywhere (conftest.py wires sys.path)
backend/.venv/bin/python -m pytest \
  backend/mcp_servers/internal/control-center-mcp-app/tests -q
```

No new dependencies: tests use `unittest.IsolatedAsyncioTestCase` (the project's
existing async-test style) plus the in-memory `fastmcp.Client`. `pytest` and
`jsonschema` are already in the environment.

## What's covered

| File | Layer | Spec / behavior verified |
|------|-------|--------------------------|
| `test_mcp_protocol_conformance.py` | Base MCP | initialize handshake, `serverInfo.name`, instructions/capabilities; every tool has a name, description, and a valid JSON-Schema `inputSchema`/`outputSchema`; unique names; resources carry uri/name/mimeType. |
| `test_mcp_apps_conformance.py` | MCP Apps | `ui://` scheme + `text/html;profile=mcp-app` mimeType + valid HTML5; `_meta.ui` (csp/domain/prefersBorder) on **both** the listing entry and the read content item; **no CSP loosening** (HTML loads only declared domains); tool→resource linkage via nested `ui.resourceUri` (deprecated flat key absent) pointing at a readable resource; `visibility` labeling for app-only / model-visible / approval tools. |
| `test_designer_draft_e2e.py` | App behavior | open/reattach/reset idempotency; offline contract resolution (`sql`/`mcp`/`airflow_python`); patch merge vs. `replace_*`; job-type swap reloads schema + resets available connectors while preserving selections; snapshot round-trips; input-validation errors; `list_job_types` static fallback when the backend is down. |
| `test_secret_redaction_e2e.py` | Security | secret FieldSpecs (`sql.params.password`, `airflow_python.config.airflow_token`) masked on AI-facing returns but preserved on the iframe-sync path; plaintext never leaks; echoed `•••` markers don't overwrite stored secrets. |
| `test_job_lifecycle_e2e.py` | App ↔ backend | `create_job` / `trigger_run` validation, normalized request-body assembly, contract-driven coercion (`port` → int), and verbatim response forwarding. |
| `test_connector_risk_profile_e2e.py` | MCP ToolAnnotations | `_classify_tool_risk` paranoid defaults (unset `destructiveHint`/`openWorldHint` ⇒ true) and risk banding; `show_connector_risk_profile` renders a valid Prefab app for both probed and unreachable connectors. |

## Mocking boundary (see `testing-anti-patterns.md`)

The **only** mocked seam is the genuine external dependency — the Control Center
HTTP API (`utils.api_get` / `utils.api_post`) and the live connector probe
(`_fetch_connector_tool_profile`). Everything above those boundaries — MCP wire
framing, schema resolution, draft state, secret masking, Prefab rendering — runs
for real. Fakes mirror the complete real response schemas (`_harness.job_out` /
`connector_out` / `run_out`), and all test setup/teardown lives in `_harness.py`,
never in `server.py`.

# Backend README

## Scope
Backend setup, run, and testing guide for the FastAPI control-plane API.

## Paths
- Backend root: `/Users/hamnatameez/toyota-control-center/backend`
- OpenAPI output: `/Users/hamnatameez/toyota-control-center/generated/openapi/openapi.json`
- TypeScript API types output: `/Users/hamnatameez/toyota-control-center/generated/types/api-types.ts`

## Python Setup
Use Python 3.10+ (3.11 recommended).

```bash
cd "/Users/hamnatameez/toyota-control-center/backend"
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
```

## Environment Config
```bash
cd "/Users/hamnatameez/toyota-control-center/backend"
cp .env.example .env
```

Key DB vars:
- `DATABASE_URL`
- `DB_SSL_MODE`
- `DB_POOL_SIZE`
- `DB_MAX_OVERFLOW`
- `DB_POOL_RECYCLE`
- `DB_POOL_PRE_PING`

OpenAI chatbot vars:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` default: `gpt-4o-mini`
- `OPENAI_TIMEOUT_SECONDS`

SQL MCP connector vars:
- `SQL_MCP_SERVER_URL`
- `SQL_MCP_SERVER_BEARER_TOKEN`
- `SQL_ANALYTICS_MCP_SERVER_URL`
- `SQL_ANALYTICS_MCP_SERVER_BEARER_TOKEN`

Scheduled job vars:
- `JOB_SCHEDULER_ENABLED` default: `true`
- `JOB_SCHEDULER_INTERVAL_SECONDS` default: `60`
- `JOB_SCHEDULER_TIMEZONE` default: `America/Chicago`

The in-process scheduler polls runtime resources with `config.schedule`, creates due runs through the same execution path as manual runs, and marks those runs with `trigger_source = "schedule"`. For local testing, root/domain-admin users can call `POST /runs/scheduler/tick` to run one scheduler pass immediately.

MCP agent LLM vars:
- `CONTROL_CENTER_MCP_MODEL` optional; defaults to `OPENAI_MODEL`
- `CONTROL_CENTER_MCP_INSTRUCTOR_MODEL` optional; defaults to `openai/{OPENAI_MODEL}`

## SQL MCP Server
The backend can execute SQL jobs through approved remote MCP servers in `src/control_center/core/registry/registry.json`:

- `sql-dab` maps to `mcp_servers/configs/sql-dab.json`
- `sql-dab-analytics` maps to `mcp_servers/configs/sql-dab-analytics.json`

Both configs expect a Streamable HTTP MCP endpoint and read the URL/token from environment variables. For local development, the included Azure Data API Builder config exposes the Control Center tables at `mcp_servers/sql-mcp-server/dab-config.json`.

### Start Local Data API Builder
Install the Data API Builder CLI if you do not already have `dab`:

```bash
dotnet tool install --global Microsoft.DataApiBuilder
```

If `dab` still shows `command not found` after install, add the default .NET tools directory to your shell PATH and reload the shell:

```bash
export PATH="$PATH:$HOME/.dotnet/tools"
```

`backend/mcp_servers/sql-mcp-server` is only a Data API Builder config directory, not a Python package. Run `python -m pip install -e .` from the backend root (`backend/`), not from `backend/mcp_servers/sql-mcp-server/`.

Start the local PostgreSQL database and run migrations first:

```bash
cd "/Users/hamnatameez/toyota-control-center/backend"
docker compose up -d postgres
source .venv/bin/activate
alembic upgrade head
```

Then start the SQL MCP server in a separate terminal:

```bash
cd "/Users/hamnatameez/toyota-control-center/backend/mcp_servers/sql-mcp-server"
export SQL_CONNECTION_STRING="Host=localhost;Port=5432;Database=control_center;Username=postgres;Password=postgres"
dab start --config dab-config.json
```

Or run the SQL MCP server through Docker Compose:

```bash
cd "/Users/hamnatameez/toyota-control-center/backend"
docker compose up -d postgres sql-mcp
```

When the SQL MCP server runs in Docker, it connects to Postgres over the Compose network using the service hostname `postgres`. The host-mapped MCP endpoint is:

```bash
http://localhost:5001/mcp
```

The manual host-run `dab start` flow typically uses:

Use the MCP URL printed by DAB. If it starts on the default local port, the MCP endpoint is typically:

```bash
http://localhost:5000/mcp
```

### Point Backend at SQL MCP
Set these in `backend/.env` before starting the FastAPI backend when the SQL MCP server is running on your host:

```bash
SQL_MCP_SERVER_URL=http://localhost:5000/mcp
SQL_MCP_SERVER_BEARER_TOKEN=local-dev-token
SQL_ANALYTICS_MCP_SERVER_URL=http://localhost:5000/mcp
SQL_ANALYTICS_MCP_SERVER_BEARER_TOKEN=local-dev-token
```

For local DAB development, `local-dev-token` can be any non-empty placeholder unless your DAB host is enforcing bearer validation. In shared or deployed environments, use the real bearer token for that MCP gateway.

If you run the backend through `docker compose`, the `api` service already points to `http://sql-mcp:5000/mcp` internally. If you run the backend on your host machine instead, keep `backend/.env` pointed at `http://localhost:5000/mcp`.
If you run the SQL MCP server through Docker Compose and the backend on your host machine, point `backend/.env` at `http://localhost:5001/mcp` instead.

### Run a SQL Job Through MCP
1. Start PostgreSQL, DAB, and the FastAPI backend.
2. Login through Swagger with `analyst@toyota.dev` and authorize with the returned bearer token.
3. Create a SQL resource:

```json
{
  "name": "runs-smoke-test",
  "kind": "runtime",
  "type": "sql",
  "connector": "sql-dab",
  "environment": "dev",
  "status": "active",
  "data_sensitivity": "low",
  "config": {
    "connection_id": "sql-dab",
    "query": "select id, status, updated_at from runs order by updated_at desc limit 5"
  },
  "tags": ["sql", "mcp", "smoke-test"]
}
```

4. Run it with `POST /resources/{resource_id}/runs`:

```json
{
  "action": "run",
  "target_environment": "dev",
  "params": {
    "query": "select id, status, updated_at from runs order by updated_at desc limit 5"
  },
  "mcp_config": {
    "server_names": ["sql-dab"],
    "prompt": "Run the supplied read-only SQL query against the approved SQL MCP server.",
    "allow_auto_selection": false
  }
}
```

For direct tool execution, set `mcp_config.tool_name` to the tool name exposed by your DAB MCP server and provide the required `tool_arguments`. If you omit `tool_name`, the Control Center MCP agent uses the configured LLM and available SQL MCP tools to complete the prompt.

### Troubleshooting SQL MCP
- If the run fails before tool execution, check `GET /integrations/mcp/servers` and confirm `sql-dab` is active.
- If the backend cannot connect, confirm `SQL_MCP_SERVER_URL` matches the DAB `/mcp` endpoint and restart FastAPI after editing `.env`.
- If DAB cannot connect to Postgres, verify `SQL_CONNECTION_STRING` and that `docker compose up -d postgres` is running.
- If an agent run fails with an LLM error, set `OPENAI_API_KEY` and `OPENAI_MODEL`, or override with `CONTROL_CENTER_MCP_MODEL`.

## Local PostgreSQL + Migrations
### Option A: Docker
```bash
cd "/Users/hamnatameez/toyota-control-center/backend"
docker compose up -d postgres
```

### Option B: Local PostgreSQL
Use your local Postgres instance and ensure database `control_center` exists.

Run migrations:
```bash
cd "/Users/hamnatameez/toyota-control-center/backend"
source .venv/bin/activate
alembic upgrade head
alembic current
```

Reset runtime data only:
```bash
cd "/Users/hamnatameez/toyota-control-center/backend"
./scripts/reset_runtime_data.sh
```

This clears local rows from `resources`, `runs`, `run_logs`, `policy_evaluations`, `approvals`, and `run_execution_status` without creating an Alembic migration.

## Run API
Always run Uvicorn via the active venv interpreter:

```bash
cd "/Users/hamnatameez/toyota-control-center/backend"
source .venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000
```

Docs:
- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## Swagger Test Workflow
1. `POST /auth/login` with one of:
```json
{"email":"analyst@toyota.dev"}
```
```json
{"email":"collections.admin@toyota.dev"}
```
```json
{"email":"root@toyota.dev"}
```
2. Copy `access_token`.
3. Click `Authorize` in Swagger and enter `Bearer <access_token>`.
4. Test core endpoints:
- `GET /resource-types`
- `POST /resources`
- `GET /resources`
- `POST /resources/{id}/runs`
- `GET /runs/{id}/status`
- `GET /runs/{id}/logs`
- `GET /runs/{id}/events/stream`
- Runtime-specific: `/resources/{id}/runtime-status`, `/runtime/health`, `/runtime/schedule`, `/runtime/heartbeat`
- Artifact-specific: `/resources/{id}/artifact/version`, `/artifact/deploy`, `/artifact/publish`

## Database Verification Commands
If `psql` is not installed:
```bash
brew install libpq
echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Connect:
```bash
psql postgresql://postgres:postgres@localhost:5432/control_center
```

Useful queries:
```sql
SELECT id,email,role,domain,is_active FROM users ORDER BY id;
SELECT id,name,kind,type,status,updated_at FROM resources ORDER BY updated_at DESC LIMIT 20;
SELECT id,resource_id,status,risk_level,requires_approval,approval_id,updated_at FROM runs ORDER BY updated_at DESC LIMIT 20;
SELECT run_id,level,message,timestamp FROM run_logs ORDER BY timestamp DESC LIMIT 50;
SELECT run_id,overall_status,risk_score,risk_level,evaluated_at FROM policy_evaluations ORDER BY evaluated_at DESC LIMIT 20;
SELECT id,run_id,status,requested_by,reviewer_id,reviewed_at FROM approvals ORDER BY created_at DESC LIMIT 20;
SELECT id,action,actor_id,created_at FROM audit_events ORDER BY created_at DESC LIMIT 50;
SELECT id,received_at FROM workflow_events ORDER BY received_at DESC LIMIT 20;
```

Exit:
```sql
\q
```

## OpenAPI + TypeScript Types
Generate API spec + TS types:
```bash
"/Users/hamnatameez/toyota-control-center/backend/scripts/export_openapi_and_types.sh"
```

## Notes
- Backend is SQL-backed via SQLAlchemy sessions.
- Seed users are created automatically when `users` table is empty.
- State-machine enforcement is active for runtime vs artifact run transitions.

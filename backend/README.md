# Backend — Toyota Control Center API

FastAPI control-plane API backed by PostgreSQL. Supports job registry, run orchestration, policy evaluation, MCP connector execution, and an AI chat assistant.

---

## Quick Start (Docker — recommended)

The entire backend stack (API + PostgreSQL) runs with a single command:

```bash
cd backend
cp .env.example .env          # fill in OPENAI_API_KEY at minimum
docker compose up --build
```

The API will be available at `http://localhost:8000`.

On first start Docker automatically:
- Boots a PostgreSQL 16 container with a persistent volume
- Builds the API image (Python 3.11 + Node 20)
- Runs the app via Uvicorn

> Migrations run automatically on startup — `alembic upgrade head` executes before the API process starts.

### Stopping and restarting

```bash
docker compose down        # stop containers, keep data volume
docker compose down -v     # stop containers and delete database volume
docker compose up          # start without rebuilding (fast)
docker compose up --build  # rebuild the image (needed after dependency changes)
```

---

## Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` with your values. Key variables:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Powers the chat assistant and MCP agent |
| `OPENAI_MODEL` | `gpt-4o` | Model used for chat and field extraction |
| `OPENAI_TIMEOUT_SECONDS` | `30` | Request timeout |
| `CONTROL_CENTER_MCP_MODEL` | *(inherits OPENAI_MODEL)* | Override model for MCP agent runs |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/control_center` | Override for production DB |
| `DB_SSL_MODE` | `local` | `local` / `require` / `verify-ca` / `verify-full` |
| `DB_POOL_SIZE` | `10` | SQLAlchemy pool size |
| `DB_MAX_OVERFLOW` | `20` | Max connections above pool size |
| `DB_POOL_RECYCLE` | `1800` | Connection recycle time (seconds) |
| `JOB_SCHEDULER_ENABLED` | `true` | Enable/disable the in-process job scheduler |
| `JOB_SCHEDULER_INTERVAL_SECONDS` | `60` | How often the scheduler polls for due jobs |
| `JOB_SCHEDULER_TIMEZONE` | `America/Chicago` | Timezone for schedule evaluation |
| `SQL_MCP_SERVER_URL` | *(optional)* | URL of the SQL MCP server endpoint |
| `SQL_MCP_SERVER_BEARER_TOKEN` | *(optional)* | Bearer token for the SQL MCP server |
| `SQL_ANALYTICS_MCP_SERVER_URL` | *(optional)* | URL of the analytics MCP server |
| `SQL_ANALYTICS_MCP_SERVER_BEARER_TOKEN` | *(optional)* | Bearer token for analytics MCP server |

When running via `docker compose`, `DATABASE_URL` is set automatically in `docker-compose.yml` to point to the Compose-managed Postgres service — you do not need to set it in `.env` for local development.

---

## Migrations

Migrations use Alembic and must be run from the host (not inside Docker).

### First-time setup

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
alembic upgrade head
```

Make sure Postgres is already running (`docker compose up -d postgres`) before running migrations.

### After pulling new migrations

```bash
source .venv/bin/activate
alembic upgrade head
alembic current          # confirm applied revision
```

### Create a new migration

```bash
source .venv/bin/activate
alembic revision --autogenerate -m "describe_your_change"
alembic upgrade head
```

---

## Local Development (without Docker)

Use this if you prefer to run the API directly on your host for faster reloads.

### 1. Start Postgres

```bash
cd backend
docker compose up -d postgres
```

### 2. Create and activate a virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Start the API

```bash
python -m uvicorn app.main:app --reload --port 8000
```

The `--reload` flag watches for file changes and restarts automatically.

---

## API Docs

Once the API is running:

| | URL |
|---|---|
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| OpenAPI JSON | `http://localhost:8000/openapi.json` |

---

## Swagger Test Workflow

1. `POST /auth/login` with one of the seed users:

```json
{ "email": "analyst@toyota.dev" }
```
```json
{ "email": "collections.admin@toyota.dev" }
```
```json
{ "email": "root@toyota.dev" }
```

2. Copy the `access_token` from the response.
3. Click **Authorize** in Swagger and enter `Bearer <access_token>`.
4. Try core endpoints:
   - `GET /jobs` — list registered jobs
   - `POST /jobs` — create a job
   - `POST /jobs/{id}/runs` — trigger a run
   - `GET /runs/{id}/logs` — fetch run logs
   - `GET /policy/{run_id}/checks` — policy evaluation for a run
   - `GET /audit` — audit event log
   - `POST /api/chat` — AI chat assistant

---

## SQL MCP Server

The backend ships a custom FastMCP SQL server at [mcp_servers/sql-mcp-server/server.py](mcp_servers/sql-mcp-server/server.py). It wraps a PostgreSQL database and exposes three MCP tools to the AI agent:

| Tool | Description |
|---|---|
| `list_tables` | Returns all user tables in the `public` schema |
| `execute_query` | Executes any SQL statement; returns up to 500 rows with a `truncated` flag |
| `execute_sql` | Compatibility alias for `execute_query` used by the direct-tool execution path |

### Connection configuration

The server reads connection details from environment variables at startup. You can provide either a single ADO.NET-style connection string or individual vars:

```bash
# Option A — single connection string (ADO.NET format)
SQL_CONNECTION_STRING=Host=localhost;Port=5432;Database=control_center;Username=postgres;Password=postgres

# Option B — individual vars
SQL_DB_HOST=localhost
SQL_DB_PORT=5432
SQL_DB_DATABASE=control_center
SQL_DB_USERNAME=postgres
SQL_DB_PASSWORD=postgres
```

Optional timeouts (seconds):

```bash
SQL_CONNECT_TIMEOUT=15   # default: 15
SQL_QUERY_TIMEOUT=30     # default: 30
```

### Running locally (stdio transport)

The server uses **stdio** transport — it is launched as a subprocess by the agent, not run as a standalone HTTP service.

```bash
cd backend/mcp_servers/sql-mcp-server
cp .env.example .env        # or edit .env directly
source .venv/bin/activate   # or use the backend venv
python server.py
```

The MCP config that tells the agent how to launch it is at [mcp_servers/configs/sql-dab.json](mcp_servers/configs/sql-dab.json):

```json
{
  "command": "python",
  "args": ["sql-mcp-server/server.py"],
  "type": "stdio",
  "env": {
    "SQL_CONNECTION_STRING": "${SQL_CONNECTION_STRING}",
    "SQL_DB_HOST": "${SQL_DB_HOST}",
    ...
  }
}
```

For a remote/HTTP-backed analytics variant, see [mcp_servers/configs/sql-dab-analytics.json](mcp_servers/configs/sql-dab-analytics.json), which uses the `streamable-http` transport and reads `SQL_ANALYTICS_MCP_SERVER_URL` / `SQL_ANALYTICS_MCP_SERVER_BEARER_TOKEN` from `.env`.

### How it integrates with job execution

When a job's `connector` field is `sql-dab`, the execution service routes the run through this MCP server. The agent receives a prompt built around the job's SQL query and calls `execute_query` (or `execute_sql`) to run it, then returns the results as structured output attached to the run log.

---

## Database Utilities

### Connect with psql

```bash
# Install psql if needed
brew install libpq
echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc

psql postgresql://postgres:postgres@localhost:5432/control_center
```

### Useful queries

```sql
SELECT id, email, role, domain FROM users ORDER BY id;
SELECT id, name, type, connector, status, updated_at FROM jobs ORDER BY updated_at DESC LIMIT 20;
SELECT id, job_id, status, trigger_source, updated_at FROM runs ORDER BY updated_at DESC LIMIT 20;
SELECT run_id, level, message, timestamp FROM run_logs ORDER BY timestamp DESC LIMIT 50;
SELECT run_id, overall_status, risk_score, risk_level FROM policy_evaluations ORDER BY evaluated_at DESC LIMIT 20;
SELECT id, action, actor_id, created_at FROM audit_events ORDER BY created_at DESC LIMIT 50;
\q
```

### Reset runtime data (dev only)

Clears runs, logs, policy evaluations, and approvals without touching schema or users:

```bash
cd backend
./scripts/reset_runtime_data.sh
```

---

## OpenAPI + TypeScript Types

Regenerate the OpenAPI spec and frontend TypeScript types after changing schemas:

```bash
cd backend
./scripts/export_openapi_and_types.sh
```

Output files:
- `generated/openapi/openapi.json`
- `generated/types/api-types.ts`

---

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py               # shared FastAPI dependencies
│   │   └── routers/              # auth, jobs, runs, policy, audit, chat, ...
│   ├── core/                     # config, database, logging
│   ├── middleware/               # audit + request-id middleware
│   ├── models/                   # SQLAlchemy ORM models
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/                 # business logic layer
│   │   ├── executors/            # MCP + GitHub write executors
│   │   └── ...
│   ├── workers/
│   │   └── tasks.py              # in-process scheduler loop
│   └── main.py                   # app factory + router wiring
├── alembic/                      # database migrations
├── mcp_servers/                  # MCP server configs
├── scripts/                      # dev utility scripts
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Notes

- Seed users are created automatically on first startup when the `users` table is empty.
- The in-process scheduler polls jobs with a `config.schedule` field and fires runs via the same execution path as manual runs, tagging them with `trigger_source = "schedule"`.
- For local testing, trigger one scheduler pass immediately with `POST /runs/scheduler/tick` (requires root or domain-admin token).
- The backend uses SQLAlchemy sessions with connection pooling; pool settings are configurable via environment variables.

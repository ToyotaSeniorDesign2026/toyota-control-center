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

> **Migrations are not run automatically by Docker.** After the first `docker compose up`, run migrations from your host (see [Migrations](#migrations) below).

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

## SQL MCP Server (optional)

The SQL MCP connector lets the agent execute SQL jobs against a Data API Builder (DAB) endpoint.

### Install DAB CLI

```bash
dotnet tool install --global Microsoft.DataApiBuilder
# If dab is not found after install:
export PATH="$PATH:$HOME/.dotnet/tools"
```

### Run DAB locally (host)

```bash
cd backend/mcp_servers/sql-mcp-server
export SQL_CONNECTION_STRING="Host=localhost;Port=5432;Database=control_center;Username=postgres;Password=postgres"
dab start --config dab-config.json
```

DAB starts on port 5000 by default. The MCP endpoint is:

```
http://localhost:5000/mcp
```

Point the backend at it in `.env`:

```bash
SQL_MCP_SERVER_URL=http://localhost:5000/mcp
SQL_MCP_SERVER_BEARER_TOKEN=local-dev-token
SQL_ANALYTICS_MCP_SERVER_URL=http://localhost:5000/mcp
SQL_ANALYTICS_MCP_SERVER_BEARER_TOKEN=local-dev-token
```

`local-dev-token` is a placeholder; DAB in local dev does not enforce bearer validation unless explicitly configured.

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
├── mcp_servers/                  # MCP server configs and local DAB setup
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

# Backend README

## Scope
Backend setup, run, and testing guide for the FastAPI control-plane API.

## Paths
- Backend root: `/Users/hamnatameez/CS 5351/toyota-control-center/backend`
- OpenAPI output: `/Users/hamnatameez/CS 5351/toyota-control-center/generated/openapi/openapi.json`
- TypeScript API types output: `/Users/hamnatameez/CS 5351/toyota-control-center/generated/types/api-types.ts`

## Python Setup
Use Python 3.10+ (3.11 recommended).

```bash
cd "/Users/hamnatameez/CS 5351/toyota-control-center/backend"
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
```

## Environment Config
```bash
cd "/Users/hamnatameez/CS 5351/toyota-control-center/backend"
cp .env.example .env
```

Key DB vars:
- `DATABASE_URL`
- `DB_SSL_MODE`
- `DB_POOL_SIZE`
- `DB_MAX_OVERFLOW`
- `DB_POOL_RECYCLE`
- `DB_POOL_PRE_PING`

## Local PostgreSQL + Migrations
### Option A: Docker
```bash
cd "/Users/hamnatameez/CS 5351/toyota-control-center/backend"
docker compose up -d postgres
```

### Option B: Local PostgreSQL
Use your local Postgres instance and ensure database `control_center` exists.

Run migrations:
```bash
cd "/Users/hamnatameez/CS 5351/toyota-control-center/backend"
source .venv/bin/activate
alembic upgrade head
alembic current
```

## Run API
Always run Uvicorn via the active venv interpreter:

```bash
cd "/Users/hamnatameez/CS 5351/toyota-control-center/backend"
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
"/Users/hamnatameez/CS 5351/toyota-control-center/backend/scripts/export_openapi_and_types.sh"
```

## Notes
- Backend is SQL-backed via SQLAlchemy sessions.
- Seed users are created automatically when `users` table is empty.
- State-machine enforcement is active for runtime vs artifact run transitions.

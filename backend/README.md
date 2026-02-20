# Backend README

## Scope
This README covers backend-only setup and workflow for the FastAPI service.

## Paths
- Backend root: `/Users/hamnatameez/toyota-control-center/backend`
- OpenAPI output: `/Users/hamnatameez/toyota-control-center/generated/openapi/openapi.json`
- TypeScript API types output: `/Users/hamnatameez/toyota-control-center/generated/types/api-types.ts`

## Python Setup
```bash
cd /Users/hamnatameez/toyota-control-center/backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

If editable install is not available in your environment:
```bash
pip install fastapi uvicorn pydantic email-validator sqlalchemy alembic "psycopg[binary]"
```

## Run API
```bash
cd /Users/hamnatameez/toyota-control-center/backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

API docs:
- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Environment Config
Copy example env file:
```bash
cd /Users/hamnatameez/toyota-control-center/backend
cp .env.example .env
```

Key DB variables:
- `DATABASE_URL`
- `DB_SSL_MODE`
- `DB_POOL_SIZE`
- `DB_MAX_OVERFLOW`
- `DB_POOL_RECYCLE`
- `DB_POOL_PRE_PING`

## Local PostgreSQL + Migrations
### Option A: Docker
```bash
cd /Users/hamnatameez/toyota-control-center/backend
docker compose up -d postgres
```

Then run migrations:
```bash
cd /Users/hamnatameez/toyota-control-center/backend
source .venv/bin/activate
alembic upgrade head
alembic current
```

### Option B: Local Postgres (no Docker)
Install PostgreSQL via Homebrew and create `control_center` database, then run the same Alembic commands.

## OpenAPI + TypeScript Types
Generate OpenAPI spec and TS types:
```bash
/Users/hamnatameez/toyota-control-center/backend/scripts/export_openapi_and_types.sh
```

This writes to separate generated folders so handwritten app code stays untouched.

## Current Implementation Note
DB infrastructure (SQLAlchemy + Alembic + migration) is in place.
Most service logic is still in-memory-backed in `app/core/db.py`.

So right now:
- You can validate DB connectivity and migrations.
- Full DB-backed API behavior still requires service-layer migration from in-memory store to SQLAlchemy session queries.

## AWS Readiness Notes
Current DB config supports local dev and AWS RDS by env vars.
For production, set `DB_SSL_MODE=require` (or stricter policy) and use environment-specific secrets.

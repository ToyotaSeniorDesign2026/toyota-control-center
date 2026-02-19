# Generated API Artifacts

This folder is intentionally separate from app code so generated files do not interfere with handwritten frontend/backend code.

## Outputs

- `openapi/openapi.json` - OpenAPI spec exported from FastAPI
- `types/api-types.ts` - TypeScript types generated from OpenAPI

## One-command generation

Run:

```bash
/Users/hamnatameez/toyota-control-center/backend/scripts/export_openapi_and_types.sh
```

## Prerequisites

- Backend virtualenv has FastAPI installed
- `openapi-typescript` available via `npx`

If dependencies are missing, install first (inside `backend/.venv`):

```bash
pip install fastapi uvicorn pydantic email-validator
npm i -D openapi-typescript
```

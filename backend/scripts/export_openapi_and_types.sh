#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/Users/hamnatameez/toyota-control-center"
BACKEND_DIR="$ROOT_DIR/backend"
OPENAPI_OUT="$ROOT_DIR/generated/openapi/openapi.json"
TS_OUT="$ROOT_DIR/generated/types/api-types.ts"

cd "$BACKEND_DIR"

PY_BIN="python3"
if command -v python3.11 >/dev/null 2>&1; then
  PY_BIN="python3.11"
fi

if [[ ! -d .venv ]]; then
  "$PY_BIN" -m venv .venv
fi

source .venv/bin/activate

# Export OpenAPI spec from FastAPI app object.
PYTHONPATH="$BACKEND_DIR" python - <<'PY'
import json
from pathlib import Path
from app.main import app

out = Path('/Users/hamnatameez/toyota-control-center/generated/openapi/openapi.json')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(app.openapi(), indent=2), encoding='utf-8')
print(f'Wrote {out}')
PY

# Generate TypeScript types into separate generated folder.
npx --yes openapi-typescript "$OPENAPI_OUT" --output "$TS_OUT"
echo "Wrote $TS_OUT"

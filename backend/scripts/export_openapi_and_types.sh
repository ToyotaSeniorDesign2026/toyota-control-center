#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
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
OPENAPI_OUT_ENV="$OPENAPI_OUT" PYTHONPATH="$BACKEND_DIR" python - <<'PY'
import json
import os
from pathlib import Path
from app.main import app

out = Path(os.environ["OPENAPI_OUT_ENV"])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(app.openapi(), indent=2), encoding='utf-8')
print(f'Wrote {out}')
PY

# Generate TypeScript types into separate generated folder.
npx --yes openapi-typescript "$OPENAPI_OUT" --output "$TS_OUT"
echo "Wrote $TS_OUT"

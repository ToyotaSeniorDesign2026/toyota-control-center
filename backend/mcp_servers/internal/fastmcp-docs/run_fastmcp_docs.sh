#!/usr/bin/env bash
set -euo pipefail

# Determine directory where this script is located
# (Ensures paths remains correct if called from other dir)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Help Menu ---
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
FastMCP Documentation Server Launcher
Usage: ./run_fastmcp_docs.sh [options] [-- <extra args for python>]

Environment Variables:
  FASTMCP_ROUTES_CSV                    Path to local route inventory
  FASTMCP_DOCS_BASE_URL                 Base URL for documentation site
  FASTMCP_DOCS_LLMS_CACHE_TTL_SECONDS   TTL for llms.txt cache (default: 1200)
  UV_CACHE_DIR                          Custom uv cache path (default: /tmp/uv-cache)

EOF
  exit 0
fi

# --- Dependency Check ---
if ! command -v uv >/dev/null 2>&1; then
  echo "Error: 'uv' not found. Please install it: https://astral.sh/uv/" >&2
  exit 1
fi

# --- Default Environment Configuration ---
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

# --- Path Resolution for Inventory ---
if [[ -z "${FASTMCP_ROUTES_CSV:-}" ]]; then
  if [[ -f "$SCRIPT_DIR/routes.csv" ]]; then
    export FASTMCP_ROUTES_CSV="$SCRIPT_DIR/routes.csv"
  else
    echo "Notice: routes.csv not found; falling back to remote llms.txt resolution." >&2
  fi
fi

# Ensure we are in the script directory
cd "$SCRIPT_DIR"

# --- Argument Parsing (direct args and "--" args) ---
PY_ARGS=()
if [[ "${1:-}" == "--" ]]; then
  shift
  PY_ARGS=("$@")
else
  PY_ARGS=("$@")
fi

# --- Execution ---
echo "Starting FastMCP Documentation Server..." >&2

# We use --with to guarantee the dependency exists regardless of local setup
# and use ${array[@]+"${array[@]}"} to safely handle empty arrays under 'set -u'
exec uv run --with "fastmcp==3.0.2" python "$SCRIPT_DIR/fastmcp_docs.py" ${PY_ARGS[@]+"${PY_ARGS[@]}"}

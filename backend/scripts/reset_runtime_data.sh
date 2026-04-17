#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"

if [[ -f ".env" ]]; then
  env_database_url="$(
    awk -F= '
      $1 == "DATABASE_URL" {
        sub(/^[^=]*=/, "", $0)
        print $0
        exit
      }
    ' .env
  )"
else
  env_database_url=""
fi

DB_URL="${DATABASE_URL:-${env_database_url:-postgresql+psycopg://postgres:postgres@localhost:5432/control_center}}"
PSQL_URL="${DB_URL/postgresql+psycopg:/postgresql:}"

psql "${PSQL_URL}" <<'SQL'
BEGIN;

DELETE FROM run_execution_status;
DELETE FROM approvals;
DELETE FROM policy_evaluations;
DELETE FROM run_logs;
DELETE FROM runs;
DELETE FROM resources;

COMMIT;

SELECT 'resources' AS table_name, COUNT(*) AS row_count FROM resources
UNION ALL
SELECT 'runs', COUNT(*) FROM runs
UNION ALL
SELECT 'run_logs', COUNT(*) FROM run_logs
UNION ALL
SELECT 'policy_evaluations', COUNT(*) FROM policy_evaluations
UNION ALL
SELECT 'approvals', COUNT(*) FROM approvals
UNION ALL
SELECT 'run_execution_status', COUNT(*) FROM run_execution_status
ORDER BY table_name;
SQL

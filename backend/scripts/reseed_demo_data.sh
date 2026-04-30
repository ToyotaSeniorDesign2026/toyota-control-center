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

echo "🔄 Clearing demo data for Collections department team members..."

psql "${PSQL_URL}" <<'SQL'
BEGIN;

-- Delete existing demo runs (from all Collections department users)
DELETE FROM run_execution_status 
WHERE run_id IN (
  SELECT r.id FROM runs r
  WHERE r.domain = 'collections'
    AND r.requested_by IN (
      SELECT id FROM users WHERE domain = 'collections' AND role = 'user'
    )
);

DELETE FROM runs 
WHERE domain = 'collections'
  AND requested_by IN (
    SELECT id FROM users WHERE domain = 'collections' AND role = 'user'
  );

-- Delete existing demo jobs (from all Collections department users)
DELETE FROM jobs 
WHERE owner_domain = 'collections'
  AND owner_id IN (
    SELECT id FROM users WHERE domain = 'collections' AND role = 'user'
  );

COMMIT;

SELECT 'Demo data cleared' AS status;
SELECT 'Jobs cleared' AS table_name, COUNT(*) AS count_remaining 
  FROM jobs 
  WHERE owner_domain = 'collections' 
    AND owner_id IN (SELECT id FROM users WHERE domain = 'collections' AND role = 'user')
UNION ALL
SELECT 'Runs cleared', COUNT(*) 
  FROM runs 
  WHERE domain = 'collections' 
    AND requested_by IN (SELECT id FROM users WHERE domain = 'collections' AND role = 'user')
ORDER BY table_name;
SQL

echo ""
echo "✅ Demo data cleared successfully!"
echo ""
echo "📋 Demo Users in Collections Department:"
echo "   - Sarah Chen (sarah.chen@toyota.dev)"
echo "   - Michael Johnson (michael.johnson@toyota.dev)"
echo "   - Jane Smith (jane.smith@toyota.dev)"
echo "   - Robert Davis (robert.davis@toyota.dev)"
echo "   - Emily Wilson (emily.wilson@toyota.dev)"
echo "   - Collections Admin (collections.admin@toyota.dev) - manages the team"
echo ""
echo "🔄 To reseed demo data with realistic jobs and runs:"
echo "   1. Stop the backend: docker compose down"
echo "   2. Start the backend: docker compose up --build"
echo "   3. Backend will automatically seed on startup"
echo ""
echo "Or quickly restart the running backend:"
echo "   docker compose restart app"
echo ""
echo "🎯 What gets seeded:"
echo "   - 5 demo users in Collections department"
echo "   - 2-3 realistic jobs per user (SQL validation, reports, ETL, etc.)"
echo "   - 5 runs per job with varied statuses (success, failure, high-risk)"
echo "   - Realistic error messages and risk scores"
echo ""
echo "👀 Department Isolation:"
echo "   - Collections Admin sees all Collections team data"
echo "   - Each analyst sees only their own jobs/runs"
echo "   - Root admin sees everything"
echo ""
echo "📊 Admin Dashboard Features:"
echo "   - Real metrics from database (active jobs, running jobs, failures)"
echo "   - Real activity feed from actual runs"
echo "   - Risk analytics calculated from real data"
echo "   - Department-scoped visibility"


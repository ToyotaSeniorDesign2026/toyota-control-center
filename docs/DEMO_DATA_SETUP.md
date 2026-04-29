# Demo Data Setup for Presentations

This guide explains how to use the demo data system for the Toyota Control Center CLI, frontend, and backend demonstrations.

## Overview

The demo data system automatically seeds the database with realistic jobs and run history for the **analyst user** (`analyst@toyota.dev`) when the backend starts. This ensures that both the CLI and frontend show the same data from the database.

### Key Features

- ✅ **Automatic seeding**: Data is created on first backend startup
- ✅ **Shared data source**: CLI and frontend read from the same database
- ✅ **Realistic data**: 5 diverse jobs with varied run statuses and timelines
- ✅ **Easy reset**: Simple script to clear and reseed data before presentations
- ✅ **No hardcoding**: Demo data lives in the database, not in code

## Demo Data Structure

### 5 Demo Jobs for Analyst User

| Job Name | Type | Connector | Sensitivity | Description |
|----------|------|-----------|------------|-------------|
| Collections Data Validation | SQL Query | sql_mcp | High | Daily SQL validation of collections database |
| Monthly Receivables Report | Excel Report | excel_mcp | High | Generate monthly receivables summary |
| Airflow Data Pipeline | Airflow DAG | airflow_mcp | Medium | Daily Airflow ETL pipeline execution |
| Executive Dashboard Report | PowerPoint | powerpoint_mcp | High | Executive leadership dashboard generation |
| Invoice Reconciliation | Data Reconciliation | sql_mcp | High | Validate invoices against AR ledger |

### Run History for Each Job

Each job has 5 runs with varied statuses and timelines:
- **5 days ago**: Completed (low risk, score: 25)
- **4 days ago**: Completed (low risk, score: 30)
- **3 days ago**: Completed (medium risk, score: 55)
- **2 hours ago**: Running (medium risk, score: 50)
- **1 hour ago**: Completed (low risk, score: 20)

This provides a realistic mix of recent activity and varied risk levels.

## How to Use Demo Data

### 1. First-Time Setup

```bash
# Start the backend (demo data auto-seeds)
cd backend
docker compose up --build

# Or with local Python:
python -m uvicorn app.main:app --reload
```

The demo data is automatically created when:
- The database is first initialized
- The `_seed_demo_jobs()` function is called during `init_db()`

### 2. Verify Demo Data is Present

#### Via CLI:
```bash
cc login
# Enter email: analyst@toyota.dev
# You should see the personalized greeting with analyst's name

cc jobs
# Should list all 5 demo jobs
```

#### Via Frontend:
```bash
# Open frontend (typically http://localhost:3000)
# Log in with analyst@toyota.dev
# Should see all 5 jobs in the jobs list
```

#### Via Database:
```bash
# Connect to PostgreSQL and verify:
SELECT COUNT(*) FROM jobs WHERE owner_id = 'u_analyst';
# Should return: 5

SELECT COUNT(*) FROM runs WHERE job_id IN 
  (SELECT id FROM jobs WHERE owner_id = 'u_analyst');
# Should return: 25 (5 jobs × 5 runs each)
```

### 3. Reset Demo Data Before Presentations

Use the provided script to clear and reseed all demo data:

```bash
# Clear existing demo data (analyst user only)
./backend/scripts/reseed_demo_data.sh

# Restart the backend to reseed
docker compose down
docker compose up --build
# OR
docker compose restart app
```

Or manually reset:

```bash
# Using psql directly:
psql postgresql://postgres:postgres@localhost:5432/control_center <<EOF
BEGIN;
DELETE FROM run_execution_status 
WHERE run_id IN (
  SELECT r.id FROM runs r
  WHERE r.job_id IN (SELECT id FROM jobs WHERE owner_id = 'u_analyst')
);
DELETE FROM runs WHERE job_id IN (SELECT id FROM jobs WHERE owner_id = 'u_analyst');
DELETE FROM jobs WHERE owner_id = 'u_analyst';
COMMIT;
EOF

# Then restart backend
```

## Demo Workflow for Presentations

### Step 1: Prepare Demo Environment

```bash
# Terminal 1: Backend
cd backend
docker compose up --build

# Wait for "Application startup complete" message
# Check logs show "Seeding demo jobs..." or similar
```

### Step 2: Verify Data is Seeded

```bash
# Terminal 2: Check database
psql postgresql://postgres:postgres@localhost:5432/control_center
SELECT name, type, status FROM jobs WHERE owner_id = 'u_analyst' ORDER BY created_at;
```

### Step 3: Demo CLI

```bash
# Terminal 3: CLI demo
cd /tmp  # Show global command works from anywhere
cc login
# Enter: analyst@toyota.dev

cc status
# Shows: ✓ Logged in as Analyst User

cc jobs
# Shows all 5 demo jobs

cc menu
# Interactive menu with jobs list and other options
```

### Step 4: Demo Frontend

```bash
# Open browser to http://localhost:3000
# Log in with analyst@toyota.dev
# Navigate to Jobs page
# Should see the same 5 jobs as CLI
```

### Step 5: Show Data Consistency

**In CLI terminal:**
```bash
cc jobs | grep "Collections Data Validation"
```

**In Frontend:**
- Navigate to Jobs page
- Verify "Collections Data Validation" appears in the list

**In Database:**
```sql
SELECT name FROM jobs WHERE name LIKE '%Collections%';
```

All three should show the same job, proving they're reading from the same database.

## Resetting Before Next Presentation

```bash
# Quick reset workflow:
./backend/scripts/reseed_demo_data.sh
docker compose restart app

# Wait for backend to start
sleep 5

# Verify demo data is restored
cc status
cc jobs
```

## Implementation Details

### Database Files Modified

- **`src/app/core/database.py`**
  - Added `_seed_demo_jobs()` function
  - Calls `_seed_demo_jobs()` during `init_db()`
  - Creates 5 realistic jobs with 5 runs each for analyst user

### Scripts Added

- **`scripts/reseed_demo_data.sh`**
  - Clears all demo jobs and runs for analyst user
  - Does NOT touch user accounts or other data
  - Reseed by restarting backend

### Demo Data Characteristics

- **Owner**: Always `u_analyst` (analyst@toyota.dev)
- **Domain**: `collections`
- **Environment**: `dev`
- **Status**: `active`
- **Tags**: `["demo", "collections", "analyst"]`
- **Data Sensitivity**: High (4 jobs), Medium (1 job)

### Seeding Logic

```
Database Startup
  ↓
init_db() runs migrations
  ↓
_seed_default_users() checks: any users exist?
  ├─ NO  → Create root, admin, analyst users → commit
  └─ YES → Skip
  ↓
_seed_demo_jobs() checks: any jobs exist?
  ├─ NO  → Create 5 demo jobs with 25 runs → commit
  └─ YES → Skip (prevents re-seeding)
```

This approach ensures:
- Demo data appears only once (on first startup)
- Users can reset/reseed with the script
- No duplicate data on subsequent restarts

## Troubleshooting

### Problem: Demo jobs don't appear

**Solution**: Check backend logs during startup
```bash
docker compose logs app | grep -i "seed\|demo"
```

If no output, run migrations manually:
```bash
cd backend
alembic upgrade head
```

### Problem: CLI sees different jobs than frontend

**Solution**: Verify both are pointing to same backend
```bash
# CLI:
cc status
# Note backend URL

# Frontend:
# Check browser console or network requests to verify backend URL
```

### Problem: Can't reset demo data

**Solution**: Check database connection and permissions
```bash
# Test database connection:
psql postgresql://postgres:postgres@localhost:5432/control_center -c "SELECT 1;"

# If connection fails, check DATABASE_URL:
cat backend/.env | grep DATABASE_URL
```

## FAQ

**Q: Will demo data be lost if I restart the backend?**
A: No, demo data persists in the database. It's only deleted by running the reseed script.

**Q: Can I modify the demo data?**
A: Yes, you can make queries directly, but it's better to use the reseed script to restore defaults.

**Q: How do I add more demo jobs?**
A: Edit the `demo_jobs_data` list in `_seed_demo_jobs()` function in `backend/src/app/core/database.py`.

**Q: What if I want different demo data for different presentations?**
A: Create a new seeding function (e.g., `_seed_sales_jobs()`) and add it to `init_db()`.

**Q: Does the analyst user exist for other logins?**
A: Yes, the analyst user is created automatically with email `analyst@toyota.dev`. The demo jobs are owned by this user.

## Next Steps

1. **First Run**: Start backend, verify demo jobs appear
2. **CLI Testing**: Test `cc login` → `cc jobs` → `cc menu`
3. **Frontend Testing**: Verify same jobs appear
4. **Database Verification**: Run SQL queries to confirm data
5. **Presentation**: Use the demo data to show end-to-end integration

---

For questions or issues, check the backend README or the database initialization code in `src/app/core/database.py`.

# Demo Data Setup - Summary

## What's Been Implemented ✅

I've set up a complete demo data system for the Toyota Control Center that allows you to demonstrate the CLI, frontend, and backend all reading from the same database.

### Changes Made

#### 1. **Backend Database Seeding** (`backend/src/app/core/database.py`)
   - Added `_seed_demo_jobs()` function that creates:
     - **5 realistic demo jobs** for the analyst user
     - **25 runs total** (5 runs per job with varied statuses and timelines)
   - Automatically called on backend startup if no jobs exist
   - Jobs include:
     1. Collections Data Validation (SQL Query)
     2. Monthly Receivables Report (Excel/Reporting)
     3. Airflow Data Pipeline (Airflow DAG)
     4. Executive Dashboard Report (PowerPoint)
     5. Invoice Reconciliation (Data Validation)

#### 2. **Reset/Reseed Script** (`backend/scripts/reseed_demo_data.sh`)
   - Easy script to clear demo data and reseed before presentations
   - Usage: `./backend/scripts/reseed_demo_data.sh`
   - Clears analyst user's jobs and runs (doesn't touch other data)
   - Restart backend to auto-reseed

#### 3. **Documentation** (`DEMO_DATA_SETUP.md`)
   - Comprehensive guide for using demo data
   - Presentation workflow instructions
   - Troubleshooting guide
   - FAQ section

## How to Verify It Works

### Step 1: Start the Backend

```bash
cd backend
docker compose up --build
```

Wait for the message: `Application startup complete`

### Step 2: Check Demo Data is Seeded

```bash
# In another terminal:
psql postgresql://postgres:postgres@localhost:5432/control_center <<EOF
SELECT COUNT(*) as job_count FROM jobs WHERE owner_id = 'u_analyst';
SELECT COUNT(*) as run_count FROM runs WHERE job_id IN (
  SELECT id FROM jobs WHERE owner_id = 'u_analyst'
);
EOF
```

**Expected output:**
```
 job_count
-----------
         5
(1 row)

 run_count
-----------
         25
(1 row)
```

### Step 3: Test with CLI

```bash
cd /Users/alexandrageer/Projects/toyota-control-center
pip install -e ./cli  # If not already installed

cc login
# Enter email: analyst@toyota.dev

cc status
# Should show: ✓ Logged in as Analyst User

cc jobs
# Should show all 5 demo jobs
```

### Step 4: Test with Frontend

```bash
# Open browser to http://localhost:3000
# Log in with: analyst@toyota.dev
# Navigate to Jobs page
# Should see the same 5 jobs as CLI
```

## Demo Job Details

| Job Name | Type | Connector | Risk Levels | Run Count |
|----------|------|-----------|-------------|-----------|
| Collections Data Validation | SQL Query | sql_mcp | Low, Medium | 5 |
| Monthly Receivables Report | Excel | excel_mcp | Low, Medium | 5 |
| Airflow Data Pipeline | Airflow DAG | airflow_mcp | Low, Medium | 5 |
| Executive Dashboard Report | PowerPoint | powerpoint_mcp | Low, Medium | 5 |
| Invoice Reconciliation | Reconciliation | sql_mcp | Low, Medium | 5 |

**Each job has 5 runs with timestamps spread over 5 days:**
- 5 days ago - Completed (Low risk, score: 25)
- 4 days ago - Completed (Low risk, score: 30)
- 3 days ago - Completed (Medium risk, score: 55)
- 2 hours ago - Running (Medium risk, score: 50)
- 1 hour ago - Completed (Low risk, score: 20)

## Reset Before Next Presentation

```bash
# Quick reset:
./backend/scripts/reseed_demo_data.sh

# Restart backend:
docker compose restart app

# Wait for startup, then verify:
cc jobs
```

## Key Features

✅ **No Hardcoding**: Demo data lives in database, not in CLI/frontend code
✅ **Single Source of Truth**: Both CLI and frontend read from same database
✅ **Automatic Seeding**: Runs on first backend startup
✅ **Easy Reset**: Simple script to reseed before presentations
✅ **Realistic Data**: 5 diverse job types with realistic run histories
✅ **Analyst User**: All data owned by `analyst@toyota.dev` (already created)

## File Locations

```
backend/
├── src/app/core/database.py          ← _seed_demo_jobs() function added
├── scripts/
│   └── reseed_demo_data.sh           ← NEW: Reset script
└── (existing migrations still work)

/
└── DEMO_DATA_SETUP.md                ← NEW: Full documentation
```

## Database Impact

- **New data only**: 5 jobs + 25 runs (only for analyst user)
- **No schema changes**: Works with existing migrations
- **Analyst user exists**: Already created by `_seed_default_users()`
- **Safe to reset**: Script only affects analyst's jobs, not other data

## Next: Presentation Workflow

```bash
# Before demo:
1. docker compose down
2. docker compose up --build
3. Verify: cc status → should show "Logged in as Analyst User"

# During demo:
4. Show CLI: cc jobs (list all 5 jobs)
5. Show Frontend: http://localhost:3000 (verify same jobs)
6. Show Database: psql query (prove single source of truth)

# After demo:
7. Run reseed script for next presentation
8. Or just do docker compose down/up
```

## No Changes Required to CLI or Frontend

The CLI and frontend **don't need any modifications**. They automatically:
- Read jobs from the backend database
- Display analyst user's jobs
- Show run history from the database

The demo data system is purely backend-based, so existing CLI and frontend code works as-is.

---

**Status**: ✅ Complete and ready for testing
**Next Step**: Start backend with `docker compose up --build` and verify with CLI/frontend

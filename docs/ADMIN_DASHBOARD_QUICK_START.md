# 🎯 Quick Start: Real Database-Backed Admin Dashboard

## What Changed?

✅ **Dashboard now uses real data** from the database instead of hardcoded values
✅ **5 realistic demo users** in Collections department with diverse jobs
✅ **New analytics API** for real metrics, activity feeds, risk analysis
✅ **Department isolation** - admin sees team data, analysts see only theirs

---

## Quick Setup

### Step 1: Reset Demo Data
```bash
cd /backend
./scripts/reseed_demo_data.sh
```

### Step 2: Restart Backend (auto-seeds)
```bash
docker compose down
docker compose up --build
```

Backend will automatically seed the database with:
- 5 analyst users in Collections department
- 14 realistic jobs (SQL, Excel, Airflow, PowerPoint, etc.)
- 70 realistic runs with varied statuses

### Step 3: Test in Dashboard

**Login as Collections Admin:**
```
Email: collections.admin@toyota.dev
Password: (use login flow)
```

→ See all 14 team jobs, all runs, team member activities

**Or login as analyst:**
```
Email: sarah.chen@toyota.dev
```

→ See only your 3 jobs and your runs

---

## Demo Users

| Email | Name | Role | Team |
|-------|------|------|------|
| collections.admin@toyota.dev | Collections Admin | domain_admin | Management |
| sarah.chen@toyota.dev | Sarah Chen | analyst | Analytics |
| michael.johnson@toyota.dev | Michael Johnson | analyst | Analytics |
| jane.smith@toyota.dev | Jane Smith | analyst | Analytics |
| robert.davis@toyota.dev | Robert Davis | analyst | Collections Ops |
| emily.wilson@toyota.dev | Emily Wilson | analyst | Collections Ops |

---

## What's Real vs Mock Now

### ✅ Real (From Database)
- **MetricsBar**: Active jobs, running jobs, failed (last 24h), pending approvals, risk alerts
- **ActivityFeed**: Recent run activities with actual user names and timestamps
- **User lists**: Real team members from database
- **Risk data**: Actual risk scores and drivers from runs

### ❌ Still Mock (For now - can be updated)
- ScheduledJobs component
- Risk analytics visualizations
- User profile stats
- Some secondary pages

---

## Department Access Control

### Collections Admin Sees
```
GET /analytics/dashboard/metrics
→ Metrics for entire Collections team (14 jobs)

GET /analytics/dashboard/activity-feed
→ All team member activities

GET /analytics/dashboard/users-in-department
→ All 5 team members with their stats
```

### Sarah Chen (Analyst) Sees
```
GET /analytics/dashboard/metrics
→ Only her metrics (3 jobs, her runs)

GET /analytics/dashboard/activity-feed
→ Only her activities

GET /analytics/dashboard/users-in-department
→ Only her user profile
```

---

## Backend Endpoints

### Metrics
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/analytics/dashboard/metrics
```

### Activity Feed
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/analytics/dashboard/activity-feed?limit=10
```

### Risk Distribution
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/analytics/dashboard/risk-distribution
```

### Risk Drivers
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/analytics/dashboard/risk-drivers
```

### Department Users
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/analytics/dashboard/users-in-department
```

### Risk Trend
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/analytics/dashboard/risk-trend?days=7
```

---

## CLI Integration

The same database is used by CLI:

```bash
# Login as Collections Admin
cc login
# Email: collections.admin@toyota.dev
cc jobs
# Shows all 14 jobs from the team

# Create a new job (also visible in dashboard)
cc create "My New Job"

# View runs (same as dashboard shows)
cc runs
```

---

## Files to Know

| File | Purpose |
|------|---------|
| `/backend/src/app/core/database.py` | Seed users and demo jobs on startup |
| `/backend/src/app/api/routers/analytics.py` | Dashboard analytics endpoints |
| `/backend/scripts/reseed_demo_data.sh` | Clear and reseed demo data |
| `/frontend/src/app/components/MetricsBar.tsx` | Dashboard header metrics |
| `/frontend/src/app/components/ActivityFeed.tsx` | Recent activity |

---

## Testing Checklist

- [ ] Backend starts without errors
- [ ] Demo data is seeded (check database)
- [ ] Collections Admin dashboard shows real metrics
- [ ] ActivityFeed shows real team member activities
- [ ] Sarah Chen sees only her own data
- [ ] Collections Admin sees all team data
- [ ] CLI shows same jobs as dashboard
- [ ] Dark mode still works
- [ ] No console errors in browser

---

## Troubleshooting

### "Dashboard shows 0 for everything"
- Check that backend is running: `docker ps`
- Check token is set: F12 > Application > localStorage > control-center-auth-token
- Check analytics endpoints are responding: curl /analytics/dashboard/metrics

### "See other people's data I shouldn't"
- This is a bug! Department isolation not working
- Check user.domain and user.role in token
- Verify backend filtering in analytics.py

### "Analytics endpoint returns 500"
- Check backend logs: `docker compose logs app`
- Might be a query error - usually has context
- Reset database: `./reseed_demo_data.sh`

### "Seed data not loading"
- Ensure database is ready: `docker compose logs db`
- Try manual reset: `docker compose exec db psql -U postgres -c "DROP DATABASE control_center; CREATE DATABASE control_center;"`
- Then restart: `docker compose restart app`

---

## Next Steps

1. **Update other dashboard components** to use real API
2. **Add risk analytics** visualizations (charts for distribution, drivers, trend)
3. **Add more demo** departments (Finance, Engineering, etc.)
4. **Create admin** management panel for user/department creation
5. **Add real-time** updates via WebSockets

---

## Questions?

See full documentation: `ADMIN_DASHBOARD_REAL_DATA.md`

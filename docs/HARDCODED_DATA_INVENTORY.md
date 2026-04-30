# Hardcoded Data Inventory - Frontend Dashboard/Admin Components

## Summary
Found **13 files** with hardcoded mock data across dashboard, approvals, promotions, risk analytics, and activity feed components.

---

## 1. Mock Job/Resource Data

### 📄 [frontend/src/app/pages/jobsData.ts](frontend/src/app/pages/jobsData.ts)
**Lines: 1-150+** - Contains multiple mock job arrays

- **`mockMyJobs`** (Line ~12): 3 approved jobs with full details
  - `customer_data_analysis` (SQL Query)
  - `sales_forecasting_agent` (AI Agent)
  - `inventory_transform` (dbt Model)
  - Each with: logs, policy checks, descriptions

- **`mockPendingApprovals`** (Line ~70): 2 pending jobs
  - `customer_sentiment_agent` (AI Agent)
  - `financial_reporting_query` (SQL Query)

- **`mockRunningJobs`** (Line ~100): Running jobs list

---

## 2. Mock Approvals Data

### 📄 [frontend/src/app/pages/Approvals.tsx](frontend/src/app/pages/Approvals.tsx)
**Lines: 17-45** - Hardcoded approval requests array

```
mockApprovals: 6 approval items with:
- APR-2024-1847: customer_segmentation_model (Risk Score: 87, High)
- APR-2024-1846: etl_customer_data_pipeline (Risk Score: 92, Critical)
- APR-2024-1845: sales_forecast_dbt (Risk Score: 45, Medium)
- APR-2024-1844: user_retention_agent (Risk Score: 78, High)
- APR-2024-1843: legacy_reporting_sql (Risk Score: 65, Medium)
- APR-2024-1842: inventory_sync_airflow (Risk Score: 38, Low)
```

---

## 3. Mock Pending Approvals (Jobs Page)

### 📄 [frontend/src/app/pages/PendingApprovals.tsx](frontend/src/app/pages/PendingApprovals.tsx)
**Line: 10** - Imports `mockPendingApprovals` from jobsData
**Lines: 51, 54** - Uses mock data to display jobs awaiting review

---

## 4. Mock Chat Threads & Activity Logs

### 📄 [frontend/src/app/pages/CreateJob.tsx](frontend/src/app/pages/CreateJob.tsx)

**Lines: 62-188** - `mockChatThreads` array with 5 chat conversations:
1. "Daily Customer Report" - chat-1
2. "ML Model Training Setup" - chat-2
3. "Database Backup Job" - chat-3
4. "API Integration Sync" - chat-4
5. "ETL Pipeline Configuration" - chat-5

**Lines: 190-195** - Mock approval and activity log data:
- **`mockApprovals`** (Line 190): 2 pending approvers
  - Data Lead (Data Governance) - pending
  - Security Officer (Compliance) - pending

- **`mockActivityLogs`** (Line 195): 3 activity entries
  - "14:32: Job created"
  - "14:31: Configuration updated"
  - "14:30: Risk assessment completed (Risk score: 45)"

---

## 5. Mock Promotions Data

### 📄 [frontend/src/app/pages/promotionsData.ts](frontend/src/app/pages/promotionsData.ts)

**Lines: 16-45** - `mockReadyForPromotion`: 3 approved resources ready for promotion
- RES-001: customer_data_analysis (SQL Query)
- RES-002: sales_forecasting_agent (AI Agent)
- RES-003: inventory_transform (dbt Model)

**Lines: 46-70** - `mockPendingPromotions`: 2 pending promotions
- RES-006: revenue_dashboard_query (Semi-Prod → Production)
- RES-007: support_ticket_classifier (Staging → Production)

**Lines: 71-97** - `mockRejectedPromotions`: 2 rejected promotions
- RES-008: customer_sentiment_agent (with rejection reason)
- RES-009: financial_reporting_query (with rejection reason)

**Lines: 98-113** - `mockRecentlyPromoted`: 1 recently promoted resource
- RES-010: user_analytics_model

---

## 6. Dashboard Metrics

### 📄 [frontend/src/app/components/MetricsBar.tsx](frontend/src/app/components/MetricsBar.tsx)
**Lines: 45-76** - Hardcoded dashboard metrics:

```
- Active Jobs: 148 (+12 this month)
- Running Now: 24 (Across all environments)
- Failed (Last 24h): 3 (2 require attention)
- Pending Approvals: 7 (Waiting for review)
- Risk Alerts: 5 (3 high priority)
- SLA Violations: 0 (Great job!)
```

---

## 7. Activity Feed

### 📄 [frontend/src/app/components/ActivityFeed.tsx](frontend/src/app/components/ActivityFeed.tsx)
**Lines: 17-45** - Hardcoded activity items (6 items):

```
1. "dbt_daily_model failed in Semi-Prod" (5 min ago) - ERROR
2. "Agent_customer_summary promoted to Prod" (15 min ago) - SUCCESS
3. "Risk score increased due to schedule change" (1 hour ago) - WARNING
4. "Policy check blocked promotion" (2 hours ago) - INFO
5. "airflow_etl_pipeline completed successfully" (3 hours ago) - SUCCESS
6. "Approaching SLA threshold for revenue_dashboard" (4 hours ago) - WARNING
```

---

## 8. Scheduled Jobs

### 📄 [frontend/src/app/components/ScheduledJobs.tsx](frontend/src/app/components/ScheduledJobs.tsx)
**Lines: 12-45** - Hardcoded scheduled jobs (5 items):

```
1. dbt_daily_model - Today 6:00 AM - Prod - SLA: < 30 min
2. customer_churn_predictor - Today 8:00 AM - Prod - SLA: < 15 min
3. revenue_dashboard - Today 9:00 AM - Prod - SLA: < 10 min
4. airflow_etl_pipeline - Today 12:00 PM - Prod - SLA: < 45 min
5. inventory_optimizer - Today 2:00 PM - Semi-Prod - SLA: < 20 min
```

---

## 9. Quick Actions

### 📄 [frontend/src/app/components/QuickActions.tsx](frontend/src/app/components/QuickActions.tsx)
**Lines: 11-25** - Hardcoded quick action buttons (4 items):

```
1. "Run Job" (Primary action)
2. "Promote to Next Environment"
3. "View Logs"
4. "Copy CLI Command"
```

---

## 10. Risk Metrics Analytics

### 📄 [frontend/src/app/components/risk/RiskMetrics.tsx](frontend/src/app/components/risk/RiskMetrics.tsx)
**Lines: 3-40** - Hardcoded risk metrics (5 items):

```
1. Average Risk Score: 62 (+5 from last week) - TREND UP
2. High Risk Jobs: 18 (+3 from last week) - TREND UP
3. Critical Changes Pending: 4 (+1 from last week) - TREND UP
4. Policy Violations (7d): 23 (-8 from last week) - TREND DOWN
5. Environment Drift Incidents: 6 (+2 from last week) - TREND UP
```

---

## 11. Risk Drivers Analysis

### 📄 [frontend/src/app/components/risk/RiskDriversSection.tsx](frontend/src/app/components/risk/RiskDriversSection.tsx)

**Lines: 15-21** - Risk drivers breakdown by percentage:
```
- Data Sensitivity: 28% (Red)
- Environment: 22% (Orange)
- Schedule/Concurrency: 18% (Orange)
- External Egress: 14% (Purple)
- Connector/Tooling: 12% (Blue)
- Cost Estimate: 6% (Indigo)
```

**Lines: 24-31** - Risk trend data (7 data points over 2 weeks):
```
- Feb 1: 58, Feb 3: 61, Feb 5: 59, Feb 7: 64
- Feb 9: 62, Feb 11: 65, Feb 13: 62
```

---

## 12. Risk Distribution Chart

### 📄 [frontend/src/app/components/risk/RiskDistributionChart.tsx](frontend/src/app/components/risk/RiskDistributionChart.tsx)
**Lines: 5-22** - Risk levels by environment:

```
DEV Environment:
  - Low: 45 jobs
  - Medium: 28 jobs
  - High: 12 jobs
  - Critical: 3 jobs

SEMI-PROD Environment:
  - Low: 32 jobs
  - Medium: 24 jobs
  - High: 15 jobs
  - Critical: 6 jobs

PRODUCTION Environment:
  - Low: 28 jobs
  - Medium: 18 jobs
  - High: 18 jobs
  - Critical: 8 jobs
```

---

## 13. Productivity Impact Metrics

### 📄 [frontend/src/app/components/research/ProductivityImpact.tsx](frontend/src/app/components/research/ProductivityImpact.tsx)
**Lines: 4-19** - Hardcoded productivity statistics:

```
- Runs automated this week: 2,847
- Manual overrides required: 34
- Estimated manual hours saved: 342 hrs
- Context switches reduced: 1,284
```

---

## 14. Required Actions Data

### 📄 [frontend/src/app/pages/requiredActionsData.ts](frontend/src/app/pages/requiredActionsData.ts)
**Lines: 10-43** - Hardcoded required action items (3 items):

```
1. act-101: "Provide deployment input: dealer_scorecard_pipeline"
   - Urgency: URGENT
   - State: PENDING
   - Required fields: dealer_region, pipeline_mode, runtime_environment

2. act-102: "Review retry policy: monthly_board_presentation"
   - Urgency: HIGH
   - State: SUCCESS
   - Details: 3 retries, 5 max allowed, 30s wait between

3. act-103: "Resolve data policy exception: finance_reporting_query"
   - Urgency: URGENT
   - State: FAILED
   - Policy: PII Data Access Control
   - Affected records: 150
```

---

## 15. Demo User Info

### 📄 [frontend/src/app/pages/LoginPage.tsx](frontend/src/app/pages/LoginPage.tsx)
**Lines: 221, 250** - Demo user credentials displayed:

```
Demo users:
- analyst@toyota.dev
- root@toyota.dev
- collections.admin@toyota.dev

Demo Mode: Any seed user email, no password required
```

---

## Summary Statistics

| Category | Count | Files |
|----------|-------|-------|
| Job/Resource Mock Data | 5+ arrays | 2 files |
| Approval Mock Data | 2 arrays | 2 files |
| Activity/Chat Data | 11 items | 2 files |
| Scheduled Jobs | 5 items | 1 file |
| Risk Metrics | 5 metrics | 1 file |
| Risk Analytics | 6 drivers + 7 trends | 2 files |
| Risk Distribution | 12 data points | 1 file |
| Productivity Stats | 4 metrics | 1 file |
| Quick Actions | 4 actions | 1 file |
| Required Actions | 3 actions | 1 file |
| Demo Users | 3 users | 1 file |

**Total: 13 files with hardcoded mock/demo data**

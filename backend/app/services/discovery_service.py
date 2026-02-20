from collections import Counter, defaultdict


def _visible_resources(db, user):
    resources = list(db.resources.values())
    if user.role == "root":
        return resources
    if user.role == "domain_admin":
        return [r for r in resources if r["owner_domain"] == user.domain]
    return [r for r in resources if r["owner_id"] == user.id]


def _visible_runs(db, user):
    runs = list(db.runs.values())
    if user.role == "root":
        return runs
    if user.role == "domain_admin":
        return [r for r in runs if r["domain"] == user.domain]
    return [r for r in runs if r["requested_by"] == user.id]


def get_insights_summary(db, user):
    runs = _visible_runs(db, user)
    resources = _visible_resources(db, user)

    total_runs = len(runs)
    succeeded = len([r for r in runs if r["status"] == "succeeded"])
    failed = len([r for r in runs if r["status"] in {"failed", "blocked"}])
    pending_approvals = len([r for r in runs if r.get("requires_approval") and r["status"] == "pending_approval"])

    avg_success_rate = round((succeeded / total_runs) * 100, 1) if total_runs else 0.0
    avg_risk_score = round(sum(r.get("risk_score", 0) for r in runs) / total_runs, 1) if total_runs else 0.0
    automation_coverage = round(min(100.0, (len(resources) / max(1, len(resources) + 2)) * 100), 1)

    return {
        "total_runs": total_runs,
        "automation_coverage_pct": automation_coverage,
        "avg_run_success_rate_pct": avg_success_rate,
        "avg_risk_score": avg_risk_score,
        "estimated_time_saved_hours": round(total_runs * 0.3, 1),
        "failed_runs": failed,
        "pending_approvals": pending_approvals,
    }


def get_insights_trends(db, user):
    runs = sorted(_visible_runs(db, user), key=lambda r: r["created_at"])
    daily = defaultdict(lambda: {"total_runs": 0, "failed_runs": 0, "ai_agent_executions": 0, "data_pipeline_runs": 0, "bi_tasks": 0})

    resources = {r["id"]: r for r in _visible_resources(db, user)}
    for run in runs:
        day = run["created_at"][:10]
        bucket = daily[day]
        bucket["total_runs"] += 1
        if run["status"] in {"failed", "blocked"}:
            bucket["failed_runs"] += 1

        rtype = (resources.get(run["resource_id"], {}).get("type") or "").lower()
        if "agent" in rtype:
            bucket["ai_agent_executions"] += 1
        elif rtype in {"airflow", "dbt", "sql", "pipeline"}:
            bucket["data_pipeline_runs"] += 1
        elif rtype in {"bi", "powerbi", "tableau", "excel", "powerpoint"}:
            bucket["bi_tasks"] += 1

    return {
        "series": [{"date": day, **vals} for day, vals in sorted(daily.items())],
        "filters": ["all", "ai_agents", "data_jobs", "bi_tasks"],
    }


def get_risk_distribution(db, user):
    runs = _visible_runs(db, user)
    levels = Counter((r.get("risk_level") or "low").lower() for r in runs)

    return {
        "risk_score_distribution": {
            "low": levels.get("low", 0),
            "medium": levels.get("medium", 0),
            "high": levels.get("high", 0),
            "critical": levels.get("critical", 0),
        },
        "risk_drivers": [
            {"name": "Data Sensitivity", "value": 28},
            {"name": "Environment", "value": 22},
            {"name": "Schedule/Concurrency", "value": 18},
            {"name": "External Egress", "value": 14},
            {"name": "Connector/Tooling", "value": 12},
            {"name": "Cost Estimate", "value": 6},
        ],
    }


def get_productivity_impact(db, user):
    runs = _visible_runs(db, user)
    automated_this_week = len(runs)

    return {
        "runs_automated_this_week": automated_this_week,
        "manual_overrides_required": len([r for r in runs if r["status"] in {"failed", "blocked"}]),
        "estimated_manual_hours_saved": round(automated_this_week * 0.3, 1),
        "context_switches_reduced": automated_this_week * 2,
        "automation_adoption_progress_pct": min(100, automated_this_week * 5),
    }


def get_environment_comparison(db, user):
    resources = _visible_resources(db, user)
    runs = _visible_runs(db, user)

    by_env = {"dev": {}, "semi-prod": {}, "prod": {}}
    for env in by_env:
        env_resources = [r for r in resources if r["environment"] == env]
        env_runs = [r for r in runs if r["target_environment"] == env]
        total_runs = len(env_runs)
        success_rate = round((len([r for r in env_runs if r["status"] == "succeeded"]) / total_runs) * 100, 1) if total_runs else 0.0
        avg_risk = round(sum(r.get("risk_score", 0) for r in env_runs) / total_runs, 1) if total_runs else 0.0

        by_env[env] = {
            "total_resources": len(env_resources),
            "success_rate_pct": success_rate,
            "avg_risk_score": avg_risk,
            "open_approvals": len([r for r in env_runs if r["status"] == "pending_approval"]),
            "sla_violations": len([r for r in env_runs if r["status"] in {"failed", "blocked"}]),
        }

    return by_env


def get_top_resources(db, user, limit: int = 10):
    resources = _visible_resources(db, user)
    runs = _visible_runs(db, user)

    run_by_resource = defaultdict(list)
    for run in runs:
        run_by_resource[run["resource_id"]].append(run)

    rows = []
    for res in resources:
        r_runs = run_by_resource.get(res["id"], [])
        total_runs = len(r_runs)
        success_rate = round((len([r for r in r_runs if r["status"] == "succeeded"]) / total_runs) * 100, 1) if total_runs else 0.0
        avg_duration = 420
        avg_risk = round(sum(r.get("risk_score", 0) for r in r_runs) / total_runs, 1) if total_runs else 20.0

        rows.append(
            {
                "resource_id": res["id"],
                "resource_name": res["name"],
                "type": res["type"],
                "total_runs": total_runs,
                "success_rate_pct": success_rate,
                "avg_duration_ms": avg_duration,
                "risk_trend": "up" if avg_risk >= 60 else "stable",
            }
        )

    rows = sorted(rows, key=lambda r: (r["total_runs"], r["success_rate_pct"]), reverse=True)
    return rows[:limit]

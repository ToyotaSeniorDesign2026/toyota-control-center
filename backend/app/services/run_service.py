from __future__ import annotations

from fastapi import HTTPException, status

from app.core.db import new_id, now_iso
from app.schemas.run import PromotionStatusOut, RunCreate
from app.services.approval_service import create_approval_request
from app.services.audit_service import write_audit
from app.services.connector_service import execute_resource
from app.services.log_service import append_run_log
from app.services.policy_service import evaluate_run_request


def _assert_run_access(user, run: dict):
    if user.role == "root":
        return
    if user.role == "domain_admin" and user.domain == run["domain"]:
        return
    if user.role == "user" and user.id == run["requested_by"]:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def create_run_and_maybe_execute(db, user, payload: RunCreate):
    resource = db.resources.get(payload.resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    if user.role != "root" and resource["owner_domain"] != user.domain and resource["owner_id"] != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    run_id = new_id("run")
    ts = now_iso()

    run = {
        "id": run_id,
        "resource_id": payload.resource_id,
        "requested_by": user.id,
        "domain": resource["owner_domain"],
        "action": payload.action,
        "target_environment": payload.target_environment,
        "status": "pending_policy",
        "risk_level": "low",
        "risk_score": 0,
        "requires_approval": False,
        "approval_id": None,
        "connector_run_id": None,
        "error": None,
        "promotion_status": "not_requested",
        "git_ref": None,
        "pr_number": None,
        "commit_sha": None,
        "workflow_run_id": None,
        "workflow_url": None,
        "created_at": ts,
        "updated_at": ts,
    }
    db.runs[run_id] = run
    append_run_log(db, run_id, "INFO", "Run created", {"resource_id": payload.resource_id})

    decision = evaluate_run_request(db, user, run)
    run["risk_level"] = decision.risk_level
    run["risk_score"] = decision.risk_score
    run["requires_approval"] = decision.requires_approval

    if decision.status in {"blocked", "pending_approval"}:
        run["status"] = decision.status
        run["updated_at"] = now_iso()
        append_run_log(db, run_id, "WARN", "Run gated by policy", {"decision": decision.model_dump()})

        if decision.requires_approval:
            approval = create_approval_request(db, user, run)
            run["approval_id"] = approval["id"]

        write_audit(db, user, "RUN_GATED", {"run_id": run_id, "status": decision.status})
        return run

    run["status"] = "executing"
    run["updated_at"] = now_iso()
    append_run_log(db, run_id, "INFO", "Connector execution started")

    result = execute_resource(db, user, run)
    run["connector_run_id"] = result["connector_run_id"]
    run["status"] = result["status"]
    run["error"] = result["error"]
    run["updated_at"] = now_iso()

    append_run_log(
        db,
        run_id,
        "INFO" if result["status"] == "succeeded" else "ERROR",
        "Connector execution finished",
        result,
    )
    write_audit(db, user, "RUN_EXECUTED", {"run_id": run_id, "status": run["status"]})
    return run


def get_run(db, user, run_id: str):
    run = db.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    _assert_run_access(user, run)
    return run


def list_runs(db, user):
    runs = list(db.runs.values())
    if user.role == "root":
        return runs
    if user.role == "domain_admin":
        return [r for r in runs if r["domain"] == user.domain]
    return [r for r in runs if r["requested_by"] == user.id]


def promote_run(
    db,
    user,
    run_id: str,
    target_environment: str,
    git_ref: str | None = None,
    pr_number: int | None = None,
    commit_sha: str | None = None,
):
    run = get_run(db, user, run_id)
    if target_environment not in {"dev", "semi-prod", "prod"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid target environment")

    run["target_environment"] = target_environment
    run["status"] = "promotion_requested"
    run["promotion_status"] = "queued"
    run["git_ref"] = git_ref
    run["pr_number"] = pr_number
    run["commit_sha"] = commit_sha
    run["updated_at"] = now_iso()

    append_run_log(
        db,
        run_id,
        "INFO",
        "Promotion requested",
        {
            "target_environment": target_environment,
            "git_ref": git_ref,
            "pr_number": pr_number,
            "commit_sha": commit_sha,
        },
    )
    write_audit(
        db,
        user,
        "RUN_PROMOTION_REQUESTED",
        {
            "run_id": run_id,
            "target_environment": target_environment,
            "git_ref": git_ref,
            "pr_number": pr_number,
            "commit_sha": commit_sha,
        },
    )
    return run


def stop_run(db, user, run_id: str):
    run = get_run(db, user, run_id)
    if run["status"] in {"succeeded", "failed", "blocked", "stopped"}:
        return run

    run["status"] = "stopped"
    run["updated_at"] = now_iso()
    append_run_log(db, run_id, "WARN", "Run stopped by user")
    write_audit(db, user, "RUN_STOPPED", {"run_id": run_id})
    return run


def retry_run(db, user, run_id: str):
    run = get_run(db, user, run_id)
    payload = RunCreate(
        resource_id=run["resource_id"],
        action=run["action"],
        target_environment=run["target_environment"],
        params={},
    )
    append_run_log(db, run_id, "INFO", "Retry requested", {"new_run": True})
    write_audit(db, user, "RUN_RETRY_REQUESTED", {"run_id": run_id})
    return create_run_and_maybe_execute(db, user, payload)


def get_run_promotion_status(db, user, run_id: str) -> PromotionStatusOut:
    run = get_run(db, user, run_id)
    return PromotionStatusOut(
        run_id=run["id"],
        resource_id=run["resource_id"],
        promotion_status=run.get("promotion_status") or "not_requested",
        target_environment=run["target_environment"],
        git_ref=run.get("git_ref"),
        pr_number=run.get("pr_number"),
        commit_sha=run.get("commit_sha"),
        workflow_run_id=run.get("workflow_run_id"),
        workflow_url=run.get("workflow_url"),
        updated_at=run["updated_at"],
    )

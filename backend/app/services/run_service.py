from __future__ import annotations

"""Run service layer: run creation/execution, state machine enforcement, and run queries."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.job import Job
from app.models.run import Run
from app.schemas.run import RunCreate
from app.services.approval_service import create_approval_request
from app.services.audit_service import write_audit
from app.services.connector_service import dispatch_execution
from app.services.execution_service import build_execution_request
from app.services.log_service import append_run_log, sync_run_execution_status
from app.services.policy_service import evaluate_run_request


_RUNTIME_TRANSITIONS = {
    "queued": {"executing", "failed", "stopped"},
    "executing": {"running", "succeeded", "failed", "stopped"},
    "running": {"succeeded", "failed", "stopped"},
    "succeeded": set(),
    "failed": set(),
    "stopped": set(),
}

_ARTIFACT_TRANSITIONS = {
    "queued": {"building", "failed"},
    "building": {"deployed", "failed"},
    "deployed": set(),
    "failed": set(),
}


def _assert_run_access(user, run: Run):
    if user.role == "root":
        return
    if user.role == "domain_admin" and user.domain == run.domain:
        return
    if user.role == "user" and user.id == run.requested_by:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def _run_kind(db: Session, run: Run) -> str:
    job = db.get(Job, run.job_id)
    return job.kind if job and job.kind else "runtime"


def _successful_completion_status(
    kind: str,
    execution_backend: str | None,
    resource_type: str | None,
    execution_status: str | None = None,
) -> str:
    if kind != "runtime":
        return "deployed"
    if execution_status == "succeeded":
        return "succeeded"
    if execution_backend == "mcp":
        return "succeeded"
    return "running"


def _can_transition(kind: str, current: str, new_status: str) -> bool:
    table = _RUNTIME_TRANSITIONS if kind == "runtime" else _ARTIFACT_TRANSITIONS
    return new_status in table.get(current, set())


def _transition_run_or_409(db: Session, run: Run, new_status: str):
    kind = _run_kind(db, run)
    current = run.status
    if current == new_status:
        return
    if not _can_transition(kind, current, new_status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid transition for {kind} run: {current} -> {new_status}",
        )
    run.status = new_status
    run.updated_at = now_iso()


def _run_to_out(run: Run) -> dict:
    return {
        "id": run.id,
        "job_id": run.job_id,
        "requested_by": run.requested_by,
        "domain": run.domain,
        "action": run.action,
        "target_environment": run.target_environment,
        "status": run.status,
        "risk_level": run.risk_level,
        "risk_score": run.risk_score,
        "requires_approval": run.requires_approval,
        "approval_id": run.approval_id,
        "connector_run_id": run.connector_run_id,
        "error": run.error,
        "promotion_status": run.promotion_status,
        "git_ref": run.git_ref,
        "pr_number": run.pr_number,
        "commit_sha": run.commit_sha,
        "workflow_run_id": run.workflow_run_id,
        "workflow_url": run.workflow_url,
        "trigger_source": run.trigger_source,
        "execution_backend": run.execution_backend,
        "execution_mode": run.execution_mode,
        "submitted_config_json": run.submitted_config_json,
        "resolved_job_spec_json": run.resolved_job_spec_json,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def create_run_and_maybe_execute(db: Session, user, payload: RunCreate, trigger_source: str = "api"):
    resource = db.get(Job, payload.job_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if user.role != "root" and resource.owner_domain != user.domain and resource.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    run_id = new_id("run")
    ts = now_iso()
    run = Run(
        id=run_id,
        job_id=payload.job_id,
        requested_by=user.id,
        domain=resource.owner_domain,
        action=payload.action,
        target_environment=payload.target_environment,
        status="queued",
        risk_level="low",
        risk_score=0,
        requires_approval=False,
        approval_id=None,
        connector_run_id=None,
        error=None,
        promotion_status="not_requested",
        git_ref=None,
        pr_number=None,
        commit_sha=None,
        workflow_run_id=None,
        workflow_url=None,
        trigger_source=None,
        execution_backend=None,
        execution_mode=None,
        submitted_config_json=None,
        resolved_job_spec_json=None,
        created_at=ts,
        updated_at=ts,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    sync_run_execution_status(db, run)
    append_run_log(db, run_id, "INFO", "Run created", {"job_id": payload.job_id})

    decision = evaluate_run_request(db, user, _run_to_out(run))
    run.risk_level = decision.risk_level
    run.risk_score = decision.risk_score
    run.requires_approval = decision.requires_approval

    if decision.status == "blocked":
        _transition_run_or_409(db, run, "failed")
        run.error = "Blocked by policy"
        db.add(run)
        db.commit()
        db.refresh(run)
        sync_run_execution_status(db, run)
        append_run_log(db, run_id, "WARN", "Run blocked by policy", {"decision": decision.model_dump()})
        write_audit(db, user, "RUN_GATED", {"run_id": run_id, "status": "blocked"})
        return _run_to_out(run)

    if decision.requires_approval:
        approval = create_approval_request(db, user, _run_to_out(run))
        run.approval_id = approval["id"]
        db.add(run)
        db.commit()
        db.refresh(run)
        sync_run_execution_status(db, run)
        append_run_log(db, run_id, "WARN", "Run waiting for approval", {"approval_id": approval["id"]})
        write_audit(db, user, "RUN_GATED", {"run_id": run_id, "status": "pending_approval"})
        return _run_to_out(run)

    kind = _run_kind(db, run)
    initial_exec_status = "executing" if kind == "runtime" else "building"
    _transition_run_or_409(db, run, initial_exec_status)
    db.add(run)
    db.commit()
    db.refresh(run)
    sync_run_execution_status(db, run)
    append_run_log(db, run_id, "INFO", f"{initial_exec_status.title()} started")

    execution_request = build_execution_request(
        run_id=run.id,
        resource=resource,
        payload=payload,
        trigger_source=trigger_source,
    )
    run.trigger_source = execution_request.trigger_source
    run.execution_backend = execution_request.execution_backend
    run.execution_mode = execution_request.execution_mode
    run.submitted_config_json = {
        "action": payload.action,
        "target_environment": payload.target_environment,
        "params": payload.params,
        "job_config": execution_request.job_config.model_dump(),
        "mcp_config": execution_request.mcp_config.model_dump(),
    }
    run.resolved_job_spec_json = execution_request.job_spec
    db.add(run)
    db.commit()
    db.refresh(run)
    sync_run_execution_status(db, run)
    append_run_log(
        db,
        run_id,
        "INFO",
        "Execution request prepared",
        {
            "execution_backend": execution_request.execution_backend,
            "execution_mode": execution_request.execution_mode,
            "trigger_source": execution_request.trigger_source,
            "job_spec": execution_request.job_spec,
        },
    )

    try:
        result = dispatch_execution(execution_request)
    except Exception as exc:
        _transition_run_or_409(db, run, "failed")
        run.error = str(exc)
        db.add(run)
        db.commit()
        db.refresh(run)
        sync_run_execution_status(db, run)
        append_run_log(
            db,
            run_id,
            "ERROR",
            "Execution failed before connector completion",
            {"error": str(exc)},
        )
        write_audit(db, user, "RUN_EXECUTED", {"run_id": run_id, "status": run.status})
        return _run_to_out(run)
    run.connector_run_id = result["connector_run_id"]

    if result["error"]:
        _transition_run_or_409(db, run, "failed")
        run.error = result["error"]
    else:
        next_status = _successful_completion_status(
            kind,
            run.execution_backend,
            resource.type,
            result.get("status"),
        )
        _transition_run_or_409(db, run, next_status)
        run.error = None
    db.add(run)
    db.commit()
    db.refresh(run)
    sync_run_execution_status(db, run)

    append_run_log(
        db,
        run_id,
        "INFO" if run.status in {"running", "succeeded", "deployed"} else "ERROR",
        "Connector execution finished",
        result,
    )
    write_audit(db, user, "RUN_EXECUTED", {"run_id": run_id, "status": run.status})
    return _run_to_out(run)


def get_run(db: Session, user, run_id: str):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    _assert_run_access(user, run)
    return _run_to_out(run)


def list_runs(db: Session, user):
    q = db.query(Run)
    if user.role == "root":
        rows = q.all()
    elif user.role == "domain_admin":
        rows = q.filter(Run.domain == user.domain).all()
    else:
        rows = q.filter(Run.requested_by == user.id).all()
    return [_run_to_out(r) for r in rows]


def query_runs(
    db: Session,
    user,
    job_id: str | None = None,
    status: str | None = None,
    updated_since: str | None = None,
    limit: int = 200,
    cursor: str | None = None,
):
    runs = sorted(list_runs(db, user), key=lambda r: r["updated_at"], reverse=True)

    if job_id:
        runs = [r for r in runs if r["job_id"] == job_id]
    if status:
        runs = [r for r in runs if r["status"].lower() == status.lower()]
    if updated_since:
        runs = [r for r in runs if r["updated_at"] >= updated_since]

    start = int(cursor) if cursor is not None else 0
    items = runs[start : start + limit]
    next_cursor = str(start + len(items)) if start + len(items) < len(runs) else None

    return {
        "items": items,
        "next_cursor": next_cursor,
    }


def stop_run(db: Session, user, run_id: str):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    _assert_run_access(user, run)

    if run.status in {"failed", "stopped", "succeeded", "deployed"}:
        return _run_to_out(run)

    kind = _run_kind(db, run)
    cancel_status = "stopped" if kind == "runtime" else "failed"
    _transition_run_or_409(db, run, cancel_status)
    if kind == "artifact":
        run.error = "Cancelled by user"
    db.add(run)
    db.commit()
    db.refresh(run)
    sync_run_execution_status(db, run)
    append_run_log(db, run_id, "WARN", "Run stopped by user")
    write_audit(db, user, "RUN_STOPPED", {"run_id": run_id})
    return _run_to_out(run)


def retry_run(db: Session, user, run_id: str):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    _assert_run_access(user, run)

    submitted = run.submitted_config_json or {}
    payload = RunCreate(
        job_id=run.job_id,
        action=submitted.get("action", run.action),
        target_environment=submitted.get("target_environment", run.target_environment),
        params=submitted.get("params", {}),
        job_config=submitted.get("job_config"),
        mcp_config=submitted.get("mcp_config"),
    )
    append_run_log(db, run_id, "INFO", "Retry requested", {"new_run": True})
    write_audit(db, user, "RUN_RETRY_REQUESTED", {"run_id": run_id})
    return create_run_and_maybe_execute(db, user, payload)

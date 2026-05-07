from __future__ import annotations

"""V2 run-execution flow.

Mirrors run_service.create_run_and_maybe_execute but dispatches via
execution_service_v2 (contract → executor_type → V2Executor) instead of the
hardcoded if-chain.

The Run is persisted exactly the same way so the existing UI / job listing /
run history all light up with the new flow.
"""

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.job import Job
from app.models.run import Run
from app.schemas.run import RunCreate
from app.services.approval_service import create_approval_request
from app.services.audit_service import write_audit
from app.services.execution_service_v2 import build_request, dispatch
from app.services.log_service import append_run_log, sync_run_execution_status
from app.services.policy_service import evaluate_run_request
from app.services.run_service import _run_to_out, _transition_run_or_409, _run_kind, _successful_completion_status

logger = logging.getLogger(__name__)


def create_run_and_execute_v2(
    db: Session,
    user,
    payload: RunCreate,
    trigger_source: str = "api",
) -> dict[str, Any]:
    """Create a Run for an existing Job and execute it via the v2 dispatch path.

    Behavior matches legacy create_run_and_maybe_execute (auth, policy, approval,
    state transitions, logs, audit) — only the executor dispatch is swapped.
    """
    job = db.get(Job, payload.job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if user.role != "root" and job.owner_domain != user.domain and job.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    run_id = new_id("run")
    ts = now_iso()
    run = Run(
        id=run_id,
        job_id=payload.job_id,
        requested_by=user.id,
        domain=job.owner_domain,
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
    append_run_log(db, run_id, "INFO", "Run created (v2)", {"job_id": payload.job_id})

    # ── Policy + approval gates (unchanged from legacy) ─────────────────────────
    decision = evaluate_run_request(db, user, _run_to_out(run))
    run.risk_level = decision.risk_level
    run.risk_score = decision.risk_score
    run.requires_approval = decision.requires_approval

    if decision.status == "blocked":
        _transition_run_or_409(db, run, "failed")
        run.error = "Blocked by policy"
        db.add(run); db.commit(); db.refresh(run)
        sync_run_execution_status(db, run)
        append_run_log(db, run_id, "WARN", "Run blocked by policy", {"decision": decision.model_dump()})
        write_audit(db, user, "RUN_GATED", {"run_id": run_id, "status": "blocked"})
        return _run_to_out(run)

    if decision.requires_approval:
        approval = create_approval_request(db, user, _run_to_out(run))
        run.approval_id = approval["id"]
        db.add(run); db.commit(); db.refresh(run)
        sync_run_execution_status(db, run)
        append_run_log(db, run_id, "WARN", "Run waiting for approval", {"approval_id": approval["id"]})
        write_audit(db, user, "RUN_GATED", {"run_id": run_id, "status": "pending_approval"})
        return _run_to_out(run)

    # ── Transition to executing ────────────────────────────────────────────────
    kind = _run_kind(db, run)
    initial_exec_status = "executing" if kind == "runtime" else "building"
    _transition_run_or_409(db, run, initial_exec_status)
    db.add(run); db.commit(); db.refresh(run)
    sync_run_execution_status(db, run)
    append_run_log(db, run_id, "INFO", f"{initial_exec_status.title()} started (v2)")

    # ── V2 dispatch ────────────────────────────────────────────────────────────
    try:
        v2_request = build_request(
            run_id=run_id,
            job=job,
            payload=payload,
            trigger_source=trigger_source,
        )
    except Exception as exc:
        _transition_run_or_409(db, run, "failed")
        run.error = f"Contract resolution failed: {exc}"
        db.add(run); db.commit(); db.refresh(run)
        sync_run_execution_status(db, run)
        append_run_log(db, run_id, "ERROR", "V2 contract resolution failed", {"error": str(exc)})
        write_audit(db, user, "RUN_EXECUTED", {"run_id": run_id, "status": run.status})
        return _run_to_out(run)

    contract = v2_request.contract
    run.trigger_source = trigger_source
    run.execution_backend = contract.executor_type.value
    run.execution_mode = contract.executor
    run.submitted_config_json = {
        "action": payload.action,
        "target_environment": payload.target_environment,
        "params": payload.params,
        "prompt": payload.prompt,
        "contract_type": contract.type,
        "executor_type": contract.executor_type.value,
        "executor": contract.executor,
    }
    db.add(run); db.commit(); db.refresh(run)
    sync_run_execution_status(db, run)
    append_run_log(
        db, run_id, "INFO", "V2 execution prepared",
        {
            "executor_type": contract.executor_type.value,
            "executor": contract.executor,
            "trigger_source": trigger_source,
        },
    )

    try:
        result = dispatch(v2_request)
    except Exception as exc:
        logger.exception("V2 dispatch raised")
        _transition_run_or_409(db, run, "failed")
        run.error = str(exc)
        db.add(run); db.commit(); db.refresh(run)
        sync_run_execution_status(db, run)
        append_run_log(db, run_id, "ERROR", "V2 dispatch raised", {"error": str(exc)})
        write_audit(db, user, "RUN_EXECUTED", {"run_id": run_id, "status": run.status})
        return _run_to_out(run)

    # ── Map v2 result to Run fields ────────────────────────────────────────────
    run.connector_run_id = f"{contract.executor_type.value}-{run_id}"
    # Store BOTH the executor's metadata block and its `result` payload (which
    # carries final_text for agents, columns/rows for tools, etc.) so the chat
    # UI / run-detail page can render whatever the executor produced.
    run.resolved_job_spec_json = {
        **(result.get("metadata") or {}),
        "executor_state": result.get("result"),
    }

    if result.get("error"):
        _transition_run_or_409(db, run, "failed")
        run.error = result["error"]
    else:
        next_status = _successful_completion_status(
            kind,
            execution_backend="mcp",  # treat all v2 paths as mcp-equivalent for completion mapping
            resource_type=job.type,
            execution_status=result.get("status"),
        )
        _transition_run_or_409(db, run, next_status)
        run.error = None

    db.add(run); db.commit(); db.refresh(run)
    sync_run_execution_status(db, run)
    append_run_log(
        db, run_id,
        "INFO" if run.status in {"running", "succeeded", "deployed"} else "ERROR",
        "V2 execution finished",
        result,
    )
    write_audit(db, user, "RUN_EXECUTED", {"run_id": run_id, "status": run.status})
    return _run_to_out(run)

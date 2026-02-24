from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.audit_event import WorkflowEvent
from app.models.run import Run
from app.schemas.integrations import GithubActionsWebhookPayload
from app.services.audit_service import write_audit
from app.services.log_service import append_run_log


_ALLOWED_STATUSES = {"queued", "in_progress", "success", "failed", "cancelled"}


def _map_status_to_promotion(status: str, conclusion: str | None) -> str:
    if status in {"queued", "in_progress"}:
        return status
    if status == "success":
        return "success"
    if status in {"failed", "cancelled"}:
        return "failed"
    if conclusion and conclusion.lower() in {"success", "failure", "cancelled"}:
        return "success" if conclusion.lower() == "success" else "failed"
    return "unknown"


def _match_run(db: Session, payload: GithubActionsWebhookPayload) -> Run | None:
    if payload.run_id:
        run = db.get(Run, payload.run_id)
        if run:
            return run

    if payload.resource_id:
        return (
            db.query(Run)
            .filter(Run.resource_id == payload.resource_id)
            .order_by(Run.updated_at.desc())
            .first()
        )

    return None


def handle_github_actions_webhook(db: Session, payload: GithubActionsWebhookPayload):
    status = payload.status.lower().strip()
    if status not in _ALLOWED_STATUSES:
        return {"ok": False, "matched_run_id": None, "message": f"Unsupported status '{payload.status}'"}

    matched_run = _match_run(db, payload)
    if not matched_run:
        db.add(
            WorkflowEvent(
                id=new_id("wev"),
                received_at=now_iso(),
                payload=payload.model_dump(),
            )
        )
        db.commit()
        return {
            "ok": True,
            "matched_run_id": None,
            "message": "Webhook accepted but no matching run found",
        }

    promotion_status = _map_status_to_promotion(status, payload.conclusion)
    matched_run.promotion_status = promotion_status
    matched_run.workflow_run_id = payload.workflow_run_id
    matched_run.workflow_url = payload.workflow_url
    matched_run.git_ref = payload.git_ref or matched_run.git_ref
    matched_run.pr_number = payload.pr_number or matched_run.pr_number
    matched_run.commit_sha = payload.commit_sha or matched_run.commit_sha
    matched_run.updated_at = now_iso()

    if promotion_status == "success":
        matched_run.status = "promoted"
    elif promotion_status == "failed":
        matched_run.status = "promotion_failed"
    elif promotion_status == "in_progress":
        matched_run.status = "promotion_in_progress"

    db.add(matched_run)
    db.commit()

    append_run_log(
        db,
        matched_run.id,
        "INFO" if promotion_status in {"queued", "in_progress", "success"} else "ERROR",
        "GitHub Actions promotion update received",
        payload.model_dump(),
    )

    write_audit(
        db,
        user=None,
        action="GITHUB_ACTIONS_WEBHOOK_RECEIVED",
        metadata={
            "matched_run_id": matched_run.id,
            "promotion_status": promotion_status,
            **payload.model_dump(),
        },
    )

    return {
        "ok": True,
        "matched_run_id": matched_run.id,
        "message": "Webhook processed",
    }

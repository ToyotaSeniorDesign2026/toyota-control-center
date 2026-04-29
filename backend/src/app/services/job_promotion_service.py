from __future__ import annotations

"""GitHub-backed job promotion for version-controlled job definitions."""

import asyncio
import re
from typing import Any

import yaml
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import new_id, now_iso
from app.models.job import Job
from app.models.run import Run
from app.services.audit_service import write_audit
from app.services.chat_mcp_service import github_write_file
from app.services.log_service import append_run_log, sync_run_execution_status


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-").lower()
    return slug or "job"


def _repo_owner_and_name(job: Job) -> tuple[str, str]:
    cfg = job.config or {}
    repo_slug = str(cfg.get("promotion_repo") or settings.toyota_jobs_repo or "").strip()
    owner = str(cfg.get("promotion_repo_owner") or settings.toyota_jobs_owner or "").strip()

    if "/" in repo_slug:
        owner_part, _, repo_part = repo_slug.partition("/")
        owner = owner or owner_part
        repo_slug = repo_part

    if not owner or not repo_slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Missing Toyota jobs repository configuration. Set TOYOTA_JOBS_OWNER "
                "and TOYOTA_JOBS_REPO, or store promotion_repo_owner/promotion_repo on the job."
            ),
        )
    return owner, repo_slug


def _promotion_branch(job: Job, action: str) -> str:
    cfg = job.config or {}
    if cfg.get("promotion_branch"):
        return str(cfg["promotion_branch"]).strip()
    if action == "publish":
        return settings.toyota_jobs_publish_branch
    return settings.toyota_jobs_deploy_branch


def _job_yaml_path(job: Job) -> str:
    cfg = job.config or {}
    if cfg.get("promotion_path"):
        return str(cfg["promotion_path"]).strip().lstrip("/")
    prefix = settings.toyota_jobs_path_prefix.strip().strip("/")
    name = _slug(job.name)
    return f"{prefix}/{job.type}/{name}.yaml"


def _job_definition(job: Job, *, action: str, run_id: str, target_environment: str) -> dict[str, Any]:
    return {
        "apiVersion": "control-center.toyota/v1",
        "kind": "Job",
        "metadata": {
            "id": job.id,
            "name": job.name,
            "type": job.type,
            "jobKind": job.kind,
            "owner": {
                "id": job.owner_id,
                "domain": job.owner_domain,
            },
            "tags": job.tags or [],
        },
        "spec": {
            "connector": job.connector,
            "environment": job.environment,
            "targetEnvironment": target_environment,
            "dataSensitivity": job.data_sensitivity,
            "config": job.config or {},
        },
        "promotion": {
            "action": action,
            "runId": run_id,
            "requestedAt": now_iso(),
        },
    }


def _write_job_yaml(
    *,
    owner: str,
    repo: str,
    path: str,
    branch: str,
    content: str,
    github_token: str,
) -> dict[str, Any]:
    return asyncio.run(
        github_write_file(
            owner=owner,
            repo=repo,
            path=path,
            content=content,
            commit_message=f"Promote Control Center job {path}",
            branch=branch,
            github_token=github_token,
            environment="dev",
        )
    )


def promote_job_via_github(db: Session, user, job: Job, action: str) -> Job:
    token = str((job.config or {}).get("github_token") or settings.github_personal_access_token or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing GitHub token. Set GITHUB_PERSONAL_ACCESS_TOKEN or job.config.github_token.",
        )

    now = now_iso()
    run_id = new_id("run")
    target_environment = "prod" if action == "publish" else "semi-prod"
    owner, repo = _repo_owner_and_name(job)
    branch = _promotion_branch(job, action)
    path = _job_yaml_path(job)
    content = yaml.safe_dump(
        _job_definition(job, action=action, run_id=run_id, target_environment=target_environment),
        sort_keys=False,
    )

    run = Run(
        id=run_id,
        job_id=job.id,
        requested_by=user.id,
        domain=job.owner_domain,
        action=action,
        target_environment=target_environment,
        status="promotion_queued",
        risk_level="low",
        risk_score=0,
        requires_approval=False,
        approval_id=None,
        connector_run_id=None,
        error=None,
        promotion_status="queued",
        git_ref=branch,
        pr_number=None,
        commit_sha=None,
        workflow_run_id=None,
        workflow_url=None,
        trigger_source="api",
        execution_backend="github_actions",
        execution_mode="job_yaml",
        submitted_config_json={
            "repo": f"{owner}/{repo}",
            "branch": branch,
            "path": path,
            "action": action,
        },
        resolved_job_spec_json=yaml.safe_load(content),
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    sync_run_execution_status(db, run)

    try:
        write_result = _write_job_yaml(
            owner=owner,
            repo=repo,
            path=path,
            branch=branch,
            content=content,
            github_token=token,
        )
    except Exception as exc:
        run.status = "promotion_failed"
        run.promotion_status = "failed"
        run.error = str(exc)
        run.updated_at = now_iso()
        db.add(run)
        db.commit()
        sync_run_execution_status(db, run)
        append_run_log(db, run.id, "ERROR", "Failed to write job.yaml to GitHub", {"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to write job.yaml to GitHub: {exc}",
        ) from exc

    job.status = "promotion_in_progress"
    job.updated_at = now_iso()
    db.add(job)
    db.commit()
    db.refresh(job)
    append_run_log(
        db,
        run.id,
        "INFO",
        "job.yaml written to Toyota jobs repository",
        {"repo": f"{owner}/{repo}", "branch": branch, "path": path, "github_result": write_result},
    )
    write_audit(
        db,
        user,
        "JOB_PROMOTION_REQUESTED",
        {"job_id": job.id, "run_id": run.id, "repo": f"{owner}/{repo}", "branch": branch, "path": path},
    )
    return job

from __future__ import annotations

"""Job service layer: SQL-backed job CRUD, filtering, and runtime/artifact actions."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.job import Job
from app.models.run import Run
from app.models.user import User
from app.schemas.job import ImportGithubRequest, JobCreate, JobUpdate
from app.services.audit_service import write_audit
from app.services.job_type_service import get_job_type_contract, validate_job_contract


def _can_access(user, job: Job) -> bool:
    if user.role == "root":
        return True
    if user.role == "domain_admin":
        return job.owner_domain == user.domain
    return job.owner_id == user.id


def _score_from_sensitivity(sensitivity: str) -> int:
    if sensitivity == "high":
        return 80
    if sensitivity == "medium":
        return 50
    return 20


def _level_from_score(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _last_run_for_job(db: Session, job_id: str) -> Run | None:
    return (
        db.query(Run)
        .filter(Run.job_id == job_id)
        .order_by(Run.updated_at.desc())
        .first()
    )


def _job_to_out(db: Session, job: Job) -> dict:
    owner = db.get(User, job.owner_id)
    last_run = _last_run_for_job(db, job.id)

    if last_run:
        risk_score = int(last_run.risk_score or 0)
        risk_level = last_run.risk_level or "low"
        last_run_at = last_run.updated_at
        last_run_status = last_run.status
    else:
        risk_score = _score_from_sensitivity(job.data_sensitivity or "low")
        risk_level = _level_from_score(risk_score)
        last_run_at = None
        last_run_status = None

    return {
        "id": job.id,
        "name": job.name,
        "kind": job.kind or "runtime",
        "type": job.type,
        "connector": job.connector,
        "owner_id": job.owner_id,
        "owner_domain": job.owner_domain,
        "environment": job.environment,
        "status": job.status,
        "data_sensitivity": job.data_sensitivity,
        "config": job.config or {},
        "tags": job.tags or [],
        "risk_score": risk_score,
        "risk_level": risk_level,
        "owner_name": owner.name if owner else None,
        "last_run_at": last_run_at,
        "last_run_status": last_run_status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _require_kind(job: Job, expected_kind: str):
    if (job.kind or "runtime") != expected_kind:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Job kind must be '{expected_kind}' for this endpoint",
        )


def create_job(db: Session, user, payload: JobCreate):
    validate_job_contract(payload.kind, payload.type, payload.config)

    job_id = new_id("job")
    ts = now_iso()
    job = Job(
        id=job_id,
        name=payload.name,
        kind=payload.kind,
        type=payload.type,
        connector=payload.connector,
        owner_id=user.id,
        owner_domain=user.domain,
        environment=payload.environment,
        status="healthy",
        data_sensitivity=payload.data_sensitivity,
        config=payload.config,
        tags=payload.tags,
        created_at=ts,
        updated_at=ts,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    write_audit(db, user, "JOB_REGISTERED", {"job_id": job_id})
    return _job_to_out(db, job)


def update_job(db: Session, user, job_id: str, payload: JobUpdate):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    updates = payload.model_dump(exclude_unset=True)
    candidate_kind = updates.get("kind", job.kind)
    candidate_type = updates.get("type", job.type)
    candidate_config = updates.get("config", job.config or {})
    validate_job_contract(candidate_kind, candidate_type, candidate_config)

    for key, value in updates.items():
        setattr(job, key, value)
    job.updated_at = now_iso()
    db.add(job)
    db.commit()
    db.refresh(job)
    write_audit(db, user, "JOB_UPDATED", {"job_id": job_id, "fields": list(updates.keys())})
    return _job_to_out(db, job)


def delete_job(db: Session, user, job_id: str):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    related_run_ids = [row[0] for row in db.query(Run.id).filter(Run.job_id == job_id).all()]
    if related_run_ids:
        from app.models.audit_event import RunLog

        db.query(RunLog).filter(RunLog.run_id.in_(related_run_ids)).delete(synchronize_session=False)
    db.query(Run).filter(Run.job_id == job_id).delete(synchronize_session=False)
    db.delete(job)
    db.commit()
    write_audit(db, user, "JOB_DELETED", {"job_id": job_id, "deleted_runs": len(related_run_ids)})


def apply_job_action(db: Session, user, job_id: str, action: str):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    action_l = action.lower()
    status_map = {
        "activate": "healthy",
        "pause": "paused",
        "deploy": "deploying",
        "publish": "published",
        "archive": "archived",
    }
    if action_l not in status_map:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported job action")
    if action_l in {"deploy", "publish"} and job.kind != "artifact":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Deploy/publish actions are only valid for artifact jobs",
        )

    job.status = status_map[action_l]
    job.updated_at = now_iso()
    db.add(job)
    db.commit()
    db.refresh(job)
    write_audit(db, user, "JOB_ACTION_APPLIED", {"job_id": job_id, "action": action_l})
    return _job_to_out(db, job)


def get_job_status(db: Session, user, job_id: str):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    _require_kind(job, "runtime")

    latest_run = _last_run_for_job(db, job.id)
    cfg = job.config or {}
    return {
        "job_id": job.id,
        "status": job.status,
        "last_run_id": latest_run.id if latest_run else None,
        "last_run_status": latest_run.status if latest_run else None,
        "last_heartbeat_at": cfg.get("last_heartbeat_at"),
        "schedule": cfg.get("schedule"),
        "updated_at": job.updated_at,
    }


def get_job_health(db: Session, user, job_id: str):
    status_out = get_job_status(db, user, job_id)
    return {
        "job_id": status_out["job_id"],
        "health": status_out["status"],
        "updated_at": status_out["updated_at"],
    }


def heartbeat_job(db: Session, user, job_id: str):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    _require_kind(job, "runtime")
    contract = get_job_type_contract(job.type)
    if contract and not contract.features.supports_heartbeat:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Type '{job.type}' does not support heartbeat",
        )

    cfg = dict(job.config or {})
    cfg["last_heartbeat_at"] = now_iso()
    job.config = cfg
    job.updated_at = now_iso()
    db.add(job)
    db.commit()
    db.refresh(job)
    write_audit(db, user, "JOB_HEARTBEAT_RECORDED", {"job_id": job_id})
    return get_job_status(db, user, job_id)


def get_job_schedule(db: Session, user, job_id: str):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    _require_kind(job, "runtime")
    cfg = job.config or {}
    return {
        "job_id": job.id,
        "schedule": cfg.get("schedule"),
        "updated_at": job.updated_at,
    }


def set_job_schedule(db: Session, user, job_id: str, schedule: str):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    _require_kind(job, "runtime")
    contract = get_job_type_contract(job.type)
    if contract and not contract.features.supports_schedule:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Type '{job.type}' does not support schedules",
        )

    cfg = dict(job.config or {})
    cfg["schedule"] = schedule
    cfg["schedule_updated_at"] = now_iso()
    job.config = cfg
    job.updated_at = now_iso()
    db.add(job)
    db.commit()
    db.refresh(job)
    write_audit(db, user, "JOB_SCHEDULE_UPDATED", {"job_id": job_id, "schedule": schedule})
    return {
        "job_id": job.id,
        "schedule": schedule,
        "updated_at": job.updated_at,
    }


def get_artifact_version(db: Session, user, job_id: str):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    _require_kind(job, "artifact")
    cfg = job.config or {}
    return {
        "job_id": job.id,
        "version": cfg.get("version", "v1"),
        "status": job.status,
        "updated_at": job.updated_at,
    }


def set_artifact_version(db: Session, user, job_id: str, version: str):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    _require_kind(job, "artifact")

    cfg = dict(job.config or {})
    cfg["version"] = version
    validate_job_contract(job.kind, job.type, cfg)
    job.config = cfg
    job.updated_at = now_iso()
    db.add(job)
    db.commit()
    db.refresh(job)
    write_audit(db, user, "ARTIFACT_VERSION_UPDATED", {"job_id": job_id, "version": version})
    return {
        "job_id": job.id,
        "version": version,
        "status": job.status,
        "updated_at": job.updated_at,
    }


def artifact_deploy(db: Session, user, job_id: str):
    return apply_job_action(db, user, job_id, "deploy")


def artifact_publish(db: Session, user, job_id: str):
    return apply_job_action(db, user, job_id, "publish")


def get_job(db: Session, user, job_id: str):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not _can_access(user, job):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return _job_to_out(db, job)


def list_jobs(db: Session, user) -> list[Job]:
    q = db.query(Job)
    if user.role == "root":
        return q.all()
    if user.role == "domain_admin":
        return q.filter(Job.owner_domain == user.domain).all()
    return q.filter(Job.owner_id == user.id).all()


def query_jobs(
    db: Session,
    user,
    q: str | None = None,
    kind: str | None = None,
    type: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
    owner: str | None = None,
    tags: str | None = None,
    env: str | None = None,
    sort: str = "updated_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 50,
):
    jobs = [_job_to_out(db, j) for j in list_jobs(db, user)]

    if q:
        ql = q.lower()
        jobs = [
            j
            for j in jobs
            if ql in j["name"].lower()
            or ql in j["id"].lower()
            or ql in (j.get("kind") or "").lower()
            or ql in j["type"].lower()
            or ql in (j.get("owner_name") or "").lower()
            or any(ql in tag.lower() for tag in j.get("tags", []))
        ]
    if kind:
        jobs = [j for j in jobs if (j.get("kind") or "").lower() == kind.lower()]
    if type:
        jobs = [j for j in jobs if j["type"].lower() == type.lower()]
    if status:
        jobs = [j for j in jobs if j["status"].lower() == status.lower()]
    if risk_level:
        jobs = [j for j in jobs if (j.get("risk_level") or "").lower() == risk_level.lower()]
    if owner:
        owner_l = owner.lower()
        jobs = [
            j
            for j in jobs
            if owner_l in (j.get("owner_name") or "").lower() or owner_l in j["owner_id"].lower()
        ]
    if tags:
        requested_tags = {t.strip().lower() for t in tags.split(",") if t.strip()}
        jobs = [j for j in jobs if requested_tags.intersection({t.lower() for t in j.get("tags", [])})]
    if env:
        jobs = [j for j in jobs if j["environment"].lower() == env.lower()]

    sort_key_map = {
        "name": lambda j: j["name"].lower(),
        "kind": lambda j: j["kind"].lower(),
        "type": lambda j: j["type"].lower(),
        "environment": lambda j: j["environment"].lower(),
        "status": lambda j: j["status"].lower(),
        "risk_score": lambda j: int(j.get("risk_score") or 0),
        "last_run_at": lambda j: j.get("last_run_at") or "",
        "updated_at": lambda j: j.get("updated_at") or "",
    }
    key_func = sort_key_map.get(sort, sort_key_map["updated_at"])
    reverse = order.lower() != "asc"
    jobs = sorted(jobs, key=key_func, reverse=reverse)

    total = len(jobs)
    start = (page - 1) * page_size
    end = start + page_size
    items = jobs[start:end]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": end < total,
    }


def search_jobs(db: Session, user, q: str | None = None, type: str | None = None, status: str | None = None, env: str | None = None):
    result = query_jobs(
        db,
        user,
        q=q,
        kind=None,
        type=type,
        status=status,
        env=env,
        page=1,
        page_size=1000,
    )
    return result["items"]


def import_jobs_from_github(db: Session, user, payload: ImportGithubRequest):
    ts = now_iso()
    job_id = new_id("job")
    generated_name = payload.path.split("/")[-1] if payload.path else payload.repo.split("/")[-1]

    config = {
        "repo": payload.repo,
        "path": payload.path,
        "ref": payload.ref,
    }
    validate_job_contract("runtime", payload.job_type, config)

    job = Job(
        id=job_id,
        name=f"{generated_name}-{payload.job_type}",
        kind="runtime",
        type=payload.job_type,
        connector="github",
        owner_id=user.id,
        owner_domain=user.domain,
        environment="dev",
        status="healthy",
        data_sensitivity="low",
        config=config,
        tags=["github-import"],
        created_at=ts,
        updated_at=ts,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    write_audit(db, user, "JOB_IMPORTED_GITHUB", {"job_id": job_id, "repo": payload.repo})

    return {
        "imported_count": 1,
        "jobs": [_job_to_out(db, job)],
    }

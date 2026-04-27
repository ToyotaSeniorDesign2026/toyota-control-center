from __future__ import annotations

"""Jobs registry/router: shared CRUD plus runtime/artifact behavior endpoints."""

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_current_user, get_db
from app.schemas.job import (
    ArtifactVersionOut,
    ArtifactVersionUpdate,
    ImportGithubRequest,
    ImportGithubResponse,
    JobCreate,
    JobListOut,
    JobOut,
    JobHealthOut,
    JobScheduleOut,
    JobScheduleUpdate,
    JobStatusOut,
    JobUpdate,
)
from app.schemas.run import RunCreate, RunCreateRequest, RunOut
from app.services.job_service import (
    apply_job_action,
    artifact_deploy,
    artifact_publish,
    create_job,
    delete_job,
    get_artifact_version,
    get_job,
    get_job_health,
    get_job_schedule,
    get_job_status,
    heartbeat_job,
    import_jobs_from_github,
    query_jobs,
    set_artifact_version,
    set_job_schedule,
    update_job,
)
from app.services.run_service import create_run_and_maybe_execute

router = APIRouter()


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def register_job(payload: JobCreate, db=Depends(get_db), user=Depends(get_current_user)):
    return create_job(db, user, payload)


@router.post("/import/github", response_model=ImportGithubResponse, status_code=status.HTTP_201_CREATED)
def import_from_github(payload: ImportGithubRequest, db=Depends(get_db), user=Depends(get_current_user)):
    return import_jobs_from_github(db, user, payload)


@router.patch("/{job_id}", response_model=JobOut)
def patch_job(job_id: str, payload: JobUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    return update_job(db, user, job_id, payload)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_job(job_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    delete_job(db, user, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{job_id}", response_model=JobOut)
def read_job(job_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_job(db, user, job_id)


@router.post("/{job_id}/actions/{action}", response_model=JobOut)
def job_action(job_id: str, action: str, db=Depends(get_db), user=Depends(get_current_user)):
    return apply_job_action(db, user, job_id, action)


@router.post("/{job_id}/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_job_run(
    job_id: str,
    payload: RunCreateRequest,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    run_payload = RunCreate(
        job_id=job_id,
        action=payload.action,
        target_environment=payload.target_environment,
        params=payload.params,
        job_config=payload.job_config,
        mcp_config=payload.mcp_config,
    )
    return create_run_and_maybe_execute(db, user, run_payload)


@router.get("/{job_id}/status", response_model=JobStatusOut)
def read_job_status(job_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_job_status(db, user, job_id)


@router.get("/{job_id}/health", response_model=JobHealthOut)
def read_job_health(job_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_job_health(db, user, job_id)


@router.post("/{job_id}/heartbeat", response_model=JobStatusOut)
def job_heartbeat(job_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return heartbeat_job(db, user, job_id)


@router.get("/{job_id}/schedule", response_model=JobScheduleOut)
def read_job_schedule(job_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_job_schedule(db, user, job_id)


@router.put("/{job_id}/schedule", response_model=JobScheduleOut)
def update_job_schedule(
    job_id: str,
    payload: JobScheduleUpdate,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return set_job_schedule(db, user, job_id, payload.schedule)


@router.get("/{job_id}/artifact/version", response_model=ArtifactVersionOut)
def read_artifact_version(job_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_artifact_version(db, user, job_id)


@router.put("/{job_id}/artifact/version", response_model=ArtifactVersionOut)
def update_artifact_version(
    job_id: str,
    payload: ArtifactVersionUpdate,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return set_artifact_version(db, user, job_id, payload.version)


@router.post("/{job_id}/artifact/deploy", response_model=JobOut)
def deploy_artifact(job_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return artifact_deploy(db, user, job_id)


@router.post("/{job_id}/artifact/publish", response_model=JobOut)
def publish_artifact(job_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return artifact_publish(db, user, job_id)


@router.get("", response_model=JobListOut)
def read_jobs(
    q: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    tags: str | None = Query(default=None, description="Comma-separated tags"),
    env: str | None = Query(default=None),
    sort: str = Query(default="updated_at"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return query_jobs(
        db,
        user,
        q=q,
        kind=kind,
        type=type,
        status=status,
        risk_level=risk_level,
        owner=owner,
        tags=tags,
        env=env,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )

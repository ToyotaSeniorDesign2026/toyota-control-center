from __future__ import annotations

"""Resource registry/router: shared CRUD plus runtime/artifact behavior endpoints."""

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_current_user, get_db
from app.schemas.resource import (
    ArtifactVersionOut,
    ArtifactVersionUpdate,
    ImportGithubRequest,
    ImportGithubResponse,
    ResourceCreate,
    ResourceListOut,
    ResourceOut,
    RuntimeHealthOut,
    RuntimeScheduleOut,
    RuntimeScheduleUpdate,
    RuntimeStatusOut,
    ResourceUpdate,
)
from app.schemas.run import RunCreate, RunCreateRequest, RunOut
from app.services.resource_service import (
    apply_resource_action,
    artifact_deploy,
    artifact_publish,
    create_resource,
    delete_resource,
    get_artifact_version,
    get_resource,
    get_runtime_health,
    get_runtime_schedule,
    get_runtime_status,
    heartbeat_runtime_resource,
    import_resources_from_github,
    query_resources,
    set_artifact_version,
    set_runtime_schedule,
    update_resource,
)
from app.services.run_service import create_run_and_maybe_execute

router = APIRouter()


@router.post("", response_model=ResourceOut, status_code=status.HTTP_201_CREATED)
def register_resource(payload: ResourceCreate, db=Depends(get_db), user=Depends(get_current_user)):
    return create_resource(db, user, payload)


@router.post("/import/github", response_model=ImportGithubResponse, status_code=status.HTTP_201_CREATED)
def import_from_github(payload: ImportGithubRequest, db=Depends(get_db), user=Depends(get_current_user)):
    return import_resources_from_github(db, user, payload)


@router.patch("/{resource_id}", response_model=ResourceOut)
def patch_resource(resource_id: str, payload: ResourceUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    return update_resource(db, user, resource_id, payload)


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_resource(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    delete_resource(db, user, resource_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{resource_id}", response_model=ResourceOut)
def read_resource(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_resource(db, user, resource_id)


@router.post("/{resource_id}/actions/{action}", response_model=ResourceOut)
def resource_action(resource_id: str, action: str, db=Depends(get_db), user=Depends(get_current_user)):
    return apply_resource_action(db, user, resource_id, action)


@router.post("/{resource_id}/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_resource_run(
    resource_id: str,
    payload: RunCreateRequest,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    run_payload = RunCreate(
        resource_id=resource_id,
        action=payload.action,
        target_environment=payload.target_environment,
        params=payload.params,
        job_config=payload.job_config,
        mcp_config=payload.mcp_config,
    )
    return create_run_and_maybe_execute(db, user, run_payload)


@router.get("/{resource_id}/runtime-status", response_model=RuntimeStatusOut)
def read_runtime_status(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_runtime_status(db, user, resource_id)


@router.get("/{resource_id}/runtime/health", response_model=RuntimeHealthOut)
def read_runtime_health(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_runtime_health(db, user, resource_id)


@router.post("/{resource_id}/runtime/heartbeat", response_model=RuntimeStatusOut)
def runtime_heartbeat(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return heartbeat_runtime_resource(db, user, resource_id)


@router.get("/{resource_id}/runtime/schedule", response_model=RuntimeScheduleOut)
def read_runtime_schedule(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_runtime_schedule(db, user, resource_id)


@router.put("/{resource_id}/runtime/schedule", response_model=RuntimeScheduleOut)
def update_runtime_schedule(
    resource_id: str,
    payload: RuntimeScheduleUpdate,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return set_runtime_schedule(db, user, resource_id, payload.schedule)


@router.get("/{resource_id}/artifact/version", response_model=ArtifactVersionOut)
def read_artifact_version(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_artifact_version(db, user, resource_id)


@router.put("/{resource_id}/artifact/version", response_model=ArtifactVersionOut)
def update_artifact_version(
    resource_id: str,
    payload: ArtifactVersionUpdate,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return set_artifact_version(db, user, resource_id, payload.version)


@router.post("/{resource_id}/artifact/deploy", response_model=ResourceOut)
def deploy_artifact(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return artifact_deploy(db, user, resource_id)


@router.post("/{resource_id}/artifact/publish", response_model=ResourceOut)
def publish_artifact(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return artifact_publish(db, user, resource_id)


@router.get("", response_model=ResourceListOut)
def read_resources(
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
    return query_resources(
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

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_current_user, get_db
from app.schemas.resource import (
    ImportGithubRequest,
    ImportGithubResponse,
    ResourceCreate,
    ResourceListOut,
    ResourceOut,
    ResourceUpdate,
)
from app.schemas.run import RunCreate, RunCreateRequest, RunOut
from app.services.resource_service import apply_resource_action, create_resource, delete_resource, get_resource, import_resources_from_github, query_resources, update_resource
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
    )
    return create_run_and_maybe_execute(db, user, run_payload)


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

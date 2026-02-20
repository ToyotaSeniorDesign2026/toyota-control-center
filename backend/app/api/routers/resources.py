from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_db
from app.schemas.resource import (
    ImportGithubRequest,
    ImportGithubResponse,
    ResourceCreate,
    ResourceListOut,
    ResourceOut,
    ResourcePromotionStatusOut,
    ResourceUpdate,
)
from app.services.resource_service import (
    create_resource,
    get_resource,
    get_resource_promotion_status,
    import_resources_from_github,
    query_resources,
    update_resource,
)

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


@router.get("/{resource_id}", response_model=ResourceOut)
def read_resource(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_resource(db, user, resource_id)


@router.get("/{resource_id}/promotion-status", response_model=ResourcePromotionStatusOut)
def read_resource_promotion_status(resource_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_resource_promotion_status(db, user, resource_id)


@router.get("", response_model=ResourceListOut)
def read_resources(
    q: str | None = Query(default=None),
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

from __future__ import annotations

"""Connectors router: manage external system connections used by jobs."""

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_current_user, get_db
from app.schemas.connector import ConnectorCreate, ConnectorListOut, ConnectorOut, ConnectorUpdate
from app.services.connector_registry_service import (
    create_connector,
    delete_connector,
    get_connector,
    query_connectors,
    update_connector,
)

router = APIRouter()


@router.post("", response_model=ConnectorOut, status_code=status.HTTP_201_CREATED)
def register_connector(payload: ConnectorCreate, db=Depends(get_db), user=Depends(get_current_user)):
    return create_connector(db, user, payload)


@router.get("", response_model=ConnectorListOut)
def read_connectors(
    connector_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    env: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return query_connectors(db, user, connector_type=connector_type, status=status, env=env, page=page, page_size=page_size)


@router.get("/{connector_id}", response_model=ConnectorOut)
def read_connector(connector_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_connector(db, user, connector_id)


@router.patch("/{connector_id}", response_model=ConnectorOut)
def patch_connector(connector_id: str, payload: ConnectorUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    return update_connector(db, user, connector_id, payload)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_connector(connector_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    delete_connector(db, user, connector_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

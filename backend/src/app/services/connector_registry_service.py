from __future__ import annotations

"""Connector registry service: CRUD for named connectors (GitHub, SQL, dbt, etc.)."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.connector import Connector
from app.schemas.connector import ConnectorCreate, ConnectorUpdate
from app.services.audit_service import write_audit

_SUPPORTED_CONNECTOR_TYPES = {
    "github",
    "sql",
    "dbt",
    "airflow",
    "microsoft",
    "mcp",
    "filesystem",
    "sharepoint",
}


def _can_access(user, connector: Connector) -> bool:
    if user.role == "root":
        return True
    if connector.is_shared:
        return True
    if user.role == "domain_admin":
        return connector.owner_domain == user.domain
    return connector.owner_id == user.id


def create_connector(db: Session, user, payload: ConnectorCreate):
    if payload.connector_type.lower() not in _SUPPORTED_CONNECTOR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported connector type '{payload.connector_type}'. Supported: {sorted(_SUPPORTED_CONNECTOR_TYPES)}",
        )

    connector_id = new_id("conn")
    ts = now_iso()
    connector = Connector(
        id=connector_id,
        name=payload.name,
        connector_type=payload.connector_type.lower(),
        owner_id=user.id,
        owner_domain=user.domain,
        environment=payload.environment,
        status="active",
        config=payload.config,
        is_shared=payload.is_shared,
        created_at=ts,
        updated_at=ts,
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    write_audit(db, user, "CONNECTOR_CREATED", {"connector_id": connector_id})
    return connector


def update_connector(db: Session, user, connector_id: str, payload: ConnectorUpdate):
    connector = db.get(Connector, connector_id)
    if not connector:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    if not _can_access(user, connector):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(connector, key, value)
    connector.updated_at = now_iso()
    db.add(connector)
    db.commit()
    db.refresh(connector)
    write_audit(db, user, "CONNECTOR_UPDATED", {"connector_id": connector_id})
    return connector


def delete_connector(db: Session, user, connector_id: str):
    connector = db.get(Connector, connector_id)
    if not connector:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    if not _can_access(user, connector):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    db.delete(connector)
    db.commit()
    write_audit(db, user, "CONNECTOR_DELETED", {"connector_id": connector_id})


def get_connector(db: Session, user, connector_id: str):
    connector = db.get(Connector, connector_id)
    if not connector:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    if not _can_access(user, connector):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return connector


def list_connectors(db: Session, user) -> list[Connector]:
    q = db.query(Connector)
    if user.role == "root":
        return q.all()
    if user.role == "domain_admin":
        return q.filter(
            (Connector.owner_domain == user.domain) | (Connector.is_shared == True)  # noqa: E712
        ).all()
    return q.filter(
        (Connector.owner_id == user.id) | (Connector.is_shared == True)  # noqa: E712
    ).all()


def query_connectors(
    db: Session,
    user,
    connector_type: str | None = None,
    status: str | None = None,
    env: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    connectors = list_connectors(db, user)

    if connector_type:
        connectors = [c for c in connectors if c.connector_type.lower() == connector_type.lower()]
    if status:
        connectors = [c for c in connectors if c.status.lower() == status.lower()]
    if env:
        connectors = [c for c in connectors if c.environment.lower() == env.lower()]

    total = len(connectors)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": connectors[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": end < total,
    }

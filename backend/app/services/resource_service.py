from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.resource import Resource
from app.models.run import Run
from app.models.user import User
from app.schemas.resource import ImportGithubRequest, ResourceCreate, ResourceUpdate
from app.services.audit_service import write_audit


def _can_access(user, resource: Resource) -> bool:
    if user.role == "root":
        return True
    if user.role == "domain_admin":
        return resource.owner_domain == user.domain
    return resource.owner_id == user.id


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


def _last_run_for_resource(db: Session, resource_id: str) -> Run | None:
    return (
        db.query(Run)
        .filter(Run.resource_id == resource_id)
        .order_by(Run.updated_at.desc())
        .first()
    )


def _resource_to_out(db: Session, resource: Resource) -> dict:
    owner = db.get(User, resource.owner_id)
    last_run = _last_run_for_resource(db, resource.id)

    if last_run:
        risk_score = int(last_run.risk_score or 0)
        risk_level = last_run.risk_level or "low"
        last_run_at = last_run.updated_at
        last_run_status = last_run.status
    else:
        risk_score = _score_from_sensitivity(resource.data_sensitivity or "low")
        risk_level = _level_from_score(risk_score)
        last_run_at = None
        last_run_status = None

    return {
        "id": resource.id,
        "name": resource.name,
        "kind": resource.kind or "runtime",
        "type": resource.type,
        "connector": resource.connector,
        "owner_id": resource.owner_id,
        "owner_domain": resource.owner_domain,
        "environment": resource.environment,
        "status": resource.status,
        "data_sensitivity": resource.data_sensitivity,
        "config": resource.config or {},
        "tags": resource.tags or [],
        "risk_score": risk_score,
        "risk_level": risk_level,
        "owner_name": owner.name if owner else None,
        "last_run_at": last_run_at,
        "last_run_status": last_run_status,
        "created_at": resource.created_at,
        "updated_at": resource.updated_at,
    }


def create_resource(db: Session, user, payload: ResourceCreate):
    resource_id = new_id("res")
    ts = now_iso()
    resource = Resource(
        id=resource_id,
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
    db.add(resource)
    db.commit()
    db.refresh(resource)
    write_audit(db, user, "RESOURCE_REGISTERED", {"resource_id": resource_id})
    return _resource_to_out(db, resource)


def update_resource(db: Session, user, resource_id: str, payload: ResourceUpdate):
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if not _can_access(user, resource):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(resource, key, value)
    resource.updated_at = now_iso()
    db.add(resource)
    db.commit()
    db.refresh(resource)
    write_audit(db, user, "RESOURCE_UPDATED", {"resource_id": resource_id, "fields": list(updates.keys())})
    return _resource_to_out(db, resource)


def delete_resource(db: Session, user, resource_id: str):
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if not _can_access(user, resource):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    related_run_ids = [row[0] for row in db.query(Run.id).filter(Run.resource_id == resource_id).all()]
    if related_run_ids:
        from app.models.audit_event import RunLog

        db.query(RunLog).filter(RunLog.run_id.in_(related_run_ids)).delete(synchronize_session=False)
    db.query(Run).filter(Run.resource_id == resource_id).delete(synchronize_session=False)
    db.delete(resource)
    db.commit()
    write_audit(db, user, "RESOURCE_DELETED", {"resource_id": resource_id, "deleted_runs": len(related_run_ids)})


def apply_resource_action(db: Session, user, resource_id: str, action: str):
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if not _can_access(user, resource):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    action_l = action.lower()
    status_map = {
        "activate": "healthy",
        "pause": "paused",
        "deploy": "deploying",
        "archive": "archived",
    }
    if action_l not in status_map:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported resource action")
    if action_l == "deploy" and resource.kind != "artifact":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Deploy action is only valid for artifact resources",
        )

    resource.status = status_map[action_l]
    resource.updated_at = now_iso()
    db.add(resource)
    db.commit()
    db.refresh(resource)
    write_audit(db, user, "RESOURCE_ACTION_APPLIED", {"resource_id": resource_id, "action": action_l})
    return _resource_to_out(db, resource)


def get_resource(db: Session, user, resource_id: str):
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if not _can_access(user, resource):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return _resource_to_out(db, resource)


def list_resources(db: Session, user) -> list[Resource]:
    q = db.query(Resource)
    if user.role == "root":
        return q.all()
    if user.role == "domain_admin":
        return q.filter(Resource.owner_domain == user.domain).all()
    return q.filter(Resource.owner_id == user.id).all()


def query_resources(
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
    resources = [_resource_to_out(db, r) for r in list_resources(db, user)]

    if q:
        ql = q.lower()
        resources = [
            r
            for r in resources
            if ql in r["name"].lower()
            or ql in r["id"].lower()
            or ql in (r.get("kind") or "").lower()
            or ql in r["type"].lower()
            or ql in (r.get("owner_name") or "").lower()
            or any(ql in tag.lower() for tag in r.get("tags", []))
        ]
    if kind:
        resources = [r for r in resources if (r.get("kind") or "").lower() == kind.lower()]
    if type:
        resources = [r for r in resources if r["type"].lower() == type.lower()]
    if status:
        resources = [r for r in resources if r["status"].lower() == status.lower()]
    if risk_level:
        resources = [r for r in resources if (r.get("risk_level") or "").lower() == risk_level.lower()]
    if owner:
        owner_l = owner.lower()
        resources = [
            r
            for r in resources
            if owner_l in (r.get("owner_name") or "").lower() or owner_l in r["owner_id"].lower()
        ]
    if tags:
        requested_tags = {t.strip().lower() for t in tags.split(",") if t.strip()}
        resources = [r for r in resources if requested_tags.intersection({t.lower() for t in r.get("tags", [])})]
    if env:
        resources = [r for r in resources if r["environment"].lower() == env.lower()]

    sort_key_map = {
        "name": lambda r: r["name"].lower(),
        "kind": lambda r: r["kind"].lower(),
        "type": lambda r: r["type"].lower(),
        "environment": lambda r: r["environment"].lower(),
        "status": lambda r: r["status"].lower(),
        "risk_score": lambda r: int(r.get("risk_score") or 0),
        "last_run_at": lambda r: r.get("last_run_at") or "",
        "updated_at": lambda r: r.get("updated_at") or "",
    }
    key_func = sort_key_map.get(sort, sort_key_map["updated_at"])
    reverse = order.lower() != "asc"
    resources = sorted(resources, key=key_func, reverse=reverse)

    total = len(resources)
    start = (page - 1) * page_size
    end = start + page_size
    items = resources[start:end]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": end < total,
    }


def search_resources(db: Session, user, q: str | None = None, type: str | None = None, status: str | None = None, env: str | None = None):
    result = query_resources(
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


def import_resources_from_github(db: Session, user, payload: ImportGithubRequest):
    ts = now_iso()
    resource_id = new_id("res")
    generated_name = payload.path.split("/")[-1] if payload.path else payload.repo.split("/")[-1]

    resource = Resource(
        id=resource_id,
        name=f"{generated_name}-{payload.resource_type}",
        kind="runtime",
        type=payload.resource_type,
        connector="github",
        owner_id=user.id,
        owner_domain=user.domain,
        environment="dev",
        status="healthy",
        data_sensitivity="low",
        config={
            "repo": payload.repo,
            "path": payload.path,
            "ref": payload.ref,
        },
        tags=["github-import"],
        created_at=ts,
        updated_at=ts,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    write_audit(db, user, "RESOURCE_IMPORTED_GITHUB", {"resource_id": resource_id, "repo": payload.repo})

    return {
        "imported_count": 1,
        "resources": [_resource_to_out(db, resource)],
    }

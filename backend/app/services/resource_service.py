from __future__ import annotations

from fastapi import HTTPException, status

from app.core.db import new_id, now_iso
from app.schemas.resource import ImportGithubRequest, ResourceCreate, ResourceUpdate
from app.services.audit_service import write_audit


def _can_access(user, resource: dict) -> bool:
    if user.role == "root":
        return True
    if user.role == "domain_admin":
        return resource["owner_domain"] == user.domain
    return resource["owner_id"] == user.id


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


def _last_run_for_resource(db, resource_id: str) -> dict | None:
    runs = [r for r in db.runs.values() if r["resource_id"] == resource_id]
    if not runs:
        return None
    return sorted(runs, key=lambda r: r["updated_at"], reverse=True)[0]


def _enrich_resource(db, resource: dict) -> dict:
    item = dict(resource)
    item.setdefault("kind", "runtime")
    owner = db.users.get(item["owner_id"])
    item["owner_name"] = owner["name"] if owner else None

    last_run = _last_run_for_resource(db, item["id"])
    if last_run:
        item["risk_score"] = int(last_run.get("risk_score", 0))
        item["risk_level"] = last_run.get("risk_level", "low")
        item["last_run_at"] = last_run.get("updated_at")
        item["last_run_status"] = last_run.get("status")
    else:
        risk_score = _score_from_sensitivity(item.get("data_sensitivity", "low"))
        item["risk_score"] = risk_score
        item["risk_level"] = _level_from_score(risk_score)
        item["last_run_at"] = None
        item["last_run_status"] = None

    item.setdefault("tags", [])
    return item


def create_resource(db, user, payload: ResourceCreate):
    resource_id = new_id("res")
    ts = now_iso()
    resource = {
        "id": resource_id,
        "name": payload.name,
        "kind": payload.kind,
        "type": payload.type,
        "connector": payload.connector,
        "owner_id": user.id,
        "owner_domain": user.domain,
        "environment": payload.environment,
        "status": "healthy",
        "data_sensitivity": payload.data_sensitivity,
        "config": payload.config,
        "tags": payload.tags,
        "created_at": ts,
        "updated_at": ts,
    }
    db.resources[resource_id] = resource
    write_audit(db, user, "RESOURCE_REGISTERED", {"resource_id": resource_id})
    return _enrich_resource(db, resource)


def update_resource(db, user, resource_id: str, payload: ResourceUpdate):
    resource = db.resources.get(resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if not _can_access(user, resource):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    updates = payload.model_dump(exclude_unset=True)
    resource.update(updates)
    resource["updated_at"] = now_iso()
    write_audit(db, user, "RESOURCE_UPDATED", {"resource_id": resource_id, "fields": list(updates.keys())})
    return _enrich_resource(db, resource)


def delete_resource(db, user, resource_id: str):
    resource = db.resources.get(resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if not _can_access(user, resource):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    related_run_ids = [run_id for run_id, run in db.runs.items() if run["resource_id"] == resource_id]
    for run_id in related_run_ids:
        db.runs.pop(run_id, None)
        db.run_logs.pop(run_id, None)
    db.resources.pop(resource_id, None)
    write_audit(db, user, "RESOURCE_DELETED", {"resource_id": resource_id, "deleted_runs": len(related_run_ids)})


def apply_resource_action(db, user, resource_id: str, action: str):
    resource = db.resources.get(resource_id)
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

    if action_l == "deploy" and resource.get("kind") != "artifact":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Deploy action is only valid for artifact resources",
        )

    resource["status"] = status_map[action_l]
    resource["updated_at"] = now_iso()
    write_audit(db, user, "RESOURCE_ACTION_APPLIED", {"resource_id": resource_id, "action": action_l})
    return _enrich_resource(db, resource)


def get_resource(db, user, resource_id: str):
    resource = db.resources.get(resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if not _can_access(user, resource):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return _enrich_resource(db, resource)


def list_resources(db, user):
    resources = list(db.resources.values())
    if user.role == "root":
        return resources
    if user.role == "domain_admin":
        return [r for r in resources if r["owner_domain"] == user.domain]
    return [r for r in resources if r["owner_id"] == user.id]


def query_resources(
    db,
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
    resources = [_enrich_resource(db, r) for r in list_resources(db, user)]

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


def search_resources(db, user, q: str | None = None, type: str | None = None, status: str | None = None, env: str | None = None):
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


def import_resources_from_github(db, user, payload: ImportGithubRequest):
    ts = now_iso()
    resource_id = new_id("res")
    generated_name = payload.path.split("/")[-1] if payload.path else payload.repo.split("/")[-1]

    resource = {
        "id": resource_id,
        "name": f"{generated_name}-{payload.resource_type}",
        "kind": "runtime",
        "type": payload.resource_type,
        "connector": "github",
        "owner_id": user.id,
        "owner_domain": user.domain,
        "environment": "dev",
        "status": "healthy",
        "data_sensitivity": "low",
        "config": {
            "repo": payload.repo,
            "path": payload.path,
            "ref": payload.ref,
        },
        "tags": ["github-import"],
        "created_at": ts,
        "updated_at": ts,
    }
    db.resources[resource_id] = resource
    write_audit(db, user, "RESOURCE_IMPORTED_GITHUB", {"resource_id": resource_id, "repo": payload.repo})

    return {
        "imported_count": 1,
        "resources": [_enrich_resource(db, resource)],
    }

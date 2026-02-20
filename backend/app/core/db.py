from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class InMemoryDB:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    resources: dict[str, dict[str, Any]] = field(default_factory=dict)
    runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    run_logs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    policy_evaluations: dict[str, dict[str, Any]] = field(default_factory=dict)
    policy_check_results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    workflow_events: list[dict[str, Any]] = field(default_factory=list)


_DB = InMemoryDB()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def seed_data() -> None:
    if _DB.users:
        return

    _DB.users = {
        "u_root": {
            "id": "u_root",
            "email": "root@toyota.local",
            "name": "Root Admin",
            "role": "root",
            "domain": "global",
            "is_active": True,
            "created_at": now_iso(),
        },
        "u_collections_admin": {
            "id": "u_collections_admin",
            "email": "collections.admin@toyota.local",
            "name": "Collections Admin",
            "role": "domain_admin",
            "domain": "collections",
            "is_active": True,
            "created_at": now_iso(),
        },
        "u_analyst": {
            "id": "u_analyst",
            "email": "analyst@toyota.local",
            "name": "Analyst User",
            "role": "user",
            "domain": "collections",
            "is_active": True,
            "created_at": now_iso(),
        },
    }


def get_db() -> InMemoryDB:
    seed_data()
    return _DB

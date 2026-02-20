from __future__ import annotations

from app.core.audit import emit_audit_event
from app.core.db import get_db


def write_audit(db, user, action: str, metadata: dict | None = None):
    actor_id = getattr(user, "id", None) if user is not None else None
    return emit_audit_event(actor_id=actor_id, action=action, metadata=metadata)


def list_audit_events(db, limit: int = 200):
    return list(reversed(db.audit_events[-limit:]))

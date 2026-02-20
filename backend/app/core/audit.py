from __future__ import annotations

from app.core.db import get_db, new_id, now_iso


def emit_audit_event(
    actor_id: str | None,
    action: str,
    metadata: dict | None = None,
) -> dict:
    db = get_db()
    event = {
        "id": new_id("aud"),
        "actor_id": actor_id,
        "action": action,
        "metadata": metadata or {},
        "created_at": now_iso(),
    }
    db.audit_events.append(event)
    return event

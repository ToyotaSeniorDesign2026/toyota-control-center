from __future__ import annotations

from app.core.database import SessionLocal
from app.core.db import new_id, now_iso
from app.models.audit_event import AuditEvent


def emit_audit_event(
    actor_id: str | None,
    action: str,
    metadata: dict | None = None,
) -> dict:
    db = SessionLocal()
    try:
        event = AuditEvent(
            id=new_id("aud"),
            actor_id=actor_id,
            action=action,
            metadata_json=metadata or {},
            created_at=now_iso(),
        )
        db.add(event)
        db.commit()
        return {
            "id": event.id,
            "actor_id": event.actor_id,
            "action": event.action,
            "metadata": event.metadata_json or {},
            "created_at": event.created_at,
        }
    finally:
        db.close()

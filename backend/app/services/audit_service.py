from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.audit_event import AuditEvent


def write_audit(db: Session, user, action: str, metadata: dict | None = None):
    actor_id = getattr(user, "id", None) if user is not None else None
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


def list_audit_events(db: Session, limit: int = 200):
    rows = (
        db.query(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "action": row.action,
            "metadata": row.metadata_json or {},
            "created_at": row.created_at,
        }
        for row in rows
    ]

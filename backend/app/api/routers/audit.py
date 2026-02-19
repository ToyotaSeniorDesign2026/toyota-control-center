from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db, require_domain_admin
from app.schemas.audit_event import AuditEventOut
from app.services.audit_service import list_audit_events

router = APIRouter()


@router.get("/events", response_model=list[AuditEventOut])
def read_audit_events(
    limit: int = Query(default=200, ge=1, le=1000),
    db=Depends(get_db),
    admin=Depends(require_domain_admin),
):
    return list_audit_events(db, limit=limit)

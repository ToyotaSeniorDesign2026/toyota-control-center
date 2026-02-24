from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.approval import Approval
from app.models.run import Run
from app.services.audit_service import write_audit


def _approval_to_out(approval: Approval) -> dict:
    return {
        "id": approval.id,
        "run_id": approval.run_id,
        "status": approval.status,
        "requested_by": approval.requested_by,
        "reviewer_id": approval.reviewer_id,
        "risk_level": approval.risk_level,
        "comment": approval.comment,
        "created_at": approval.created_at,
        "reviewed_at": approval.reviewed_at,
    }


def create_approval_request(db: Session, user, run: dict):
    approval_id = new_id("apr")
    approval = Approval(
        id=approval_id,
        run_id=run["id"],
        status="pending",
        requested_by=user.id,
        reviewer_id=None,
        risk_level=run["risk_level"],
        comment=None,
        created_at=now_iso(),
        reviewed_at=None,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return _approval_to_out(approval)


def approve_request(db: Session, admin, approval_id: str):
    approval = db.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    approval.status = "approved"
    approval.reviewer_id = admin.id
    approval.reviewed_at = now_iso()

    run = db.get(Run, approval.run_id)
    if run:
        run.status = "approved"
        run.updated_at = now_iso()
        db.add(run)

    db.add(approval)
    db.commit()
    db.refresh(approval)

    write_audit(db, admin, "APPROVAL_GRANTED", {"approval_id": approval_id, "run_id": approval.run_id})
    return _approval_to_out(approval)

from fastapi import HTTPException, status

from app.core.db import new_id, now_iso
from app.services.audit_service import write_audit


def create_approval_request(db, user, run: dict):
    approval_id = new_id("apr")
    approval = {
        "id": approval_id,
        "run_id": run["id"],
        "status": "pending",
        "requested_by": user.id,
        "reviewer_id": None,
        "risk_level": run["risk_level"],
        "comment": None,
        "created_at": now_iso(),
        "reviewed_at": None,
    }
    db.approvals[approval_id] = approval
    return approval


def approve_request(db, admin, approval_id: str):
    approval = db.approvals.get(approval_id)
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    approval["status"] = "approved"
    approval["reviewer_id"] = admin.id
    approval["reviewed_at"] = now_iso()

    run = db.runs.get(approval["run_id"])
    if run:
        run["status"] = "approved"
        run["updated_at"] = now_iso()

    write_audit(db, admin, "APPROVAL_GRANTED", {"approval_id": approval_id, "run_id": approval["run_id"]})
    return approval

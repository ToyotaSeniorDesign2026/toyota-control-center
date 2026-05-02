from __future__ import annotations

<<<<<<< HEAD
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_db, require_domain_admin
from app.schemas.approval import ApprovalOut, ApprovalRejectRequest
from app.schemas.policy import PolicyEvaluationOut
from app.services.approval_service import approve_request, list_approvals, reject_request
=======
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_db, require_domain_admin
from app.schemas.approval import ApprovalOut
from app.schemas.policy import PolicyEvaluationOut
from app.services.approval_service import approve_request
>>>>>>> polishing-agent-chat
from app.services.policy_service import get_policy_checks_for_run

router = APIRouter()


@router.get("/runs/{run_id}/checks", response_model=PolicyEvaluationOut | None)
def policy_checks(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_policy_checks_for_run(db, user, run_id)


<<<<<<< HEAD
@router.get("/approvals", response_model=list[ApprovalOut])
def approvals(
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db=Depends(get_db),
    admin=Depends(require_domain_admin),
):
    return list_approvals(db, admin, status_filter=status, limit=limit)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalOut)
def approve(approval_id: str, db=Depends(get_db), admin=Depends(require_domain_admin)):
    return approve_request(db, admin, approval_id)


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalOut)
def reject(
    approval_id: str,
    payload: ApprovalRejectRequest,
    db=Depends(get_db),
    admin=Depends(require_domain_admin),
):
    return reject_request(db, admin, approval_id, comment=payload.comment)
=======
@router.post("/approvals/{approval_id}/approve", response_model=ApprovalOut)
def approve(approval_id: str, db=Depends(get_db), admin=Depends(require_domain_admin)):
    return approve_request(db, admin, approval_id)
>>>>>>> polishing-agent-chat

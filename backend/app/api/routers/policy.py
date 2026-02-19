from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_db, require_domain_admin
from app.schemas.approval import ApprovalOut
from app.schemas.policy import PolicyEvaluationOut
from app.services.approval_service import approve_request
from app.services.policy_service import get_policy_checks_for_run

router = APIRouter()


@router.get("/runs/{run_id}/checks", response_model=PolicyEvaluationOut | None)
def policy_checks(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_policy_checks_for_run(db, user, run_id)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalOut)
def approve(approval_id: str, db=Depends(get_db), admin=Depends(require_domain_admin)):
    return approve_request(db, admin, approval_id)

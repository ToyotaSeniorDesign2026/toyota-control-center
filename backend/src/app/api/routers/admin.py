"""Admin router: Department-level access to users, jobs, runs, and approval workflows."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.approval import Approval
from app.models.job import Job
from app.models.run import Run
from app.models.user import User
from app.schemas.user import UserOut
from app.core.db import now_iso, new_id

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(user: User):
    """Ensure user is a domain admin or root admin."""
    if user.role not in ("root", "domain_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this endpoint"
        )


def _get_department_domain(user: User) -> str:
    """Get the domain/department context for the admin."""
    if user.role == "root":
        return "*"  # Root can see all
    return user.domain


# ============================================================================
# USERS ENDPOINTS
# ============================================================================

@router.get("/users", response_model=dict)
def list_department_users(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List all users in the admin's department."""
    _require_admin(user)
    domain = _get_department_domain(user)
    
    if domain == "*":
        users = db.query(User).filter(User.is_active.is_(True)).all()
    else:
        users = db.query(User).filter(
            User.domain == domain,
            User.is_active.is_(True)
        ).all()
    
    return {
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "domain": u.domain,
                "job_title": u.job_title,
                "department": u.department,
                "team": u.team,
                "is_active": u.is_active,
                "created_at": u.created_at,
            }
            for u in users
        ],
        "count": len(users)
    }


# ============================================================================
# JOBS ENDPOINTS
# ============================================================================

@router.get("/jobs", response_model=dict)
def list_department_jobs(
    status_filter: str = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List all jobs owned by users in the admin's department."""
    _require_admin(user)
    domain = _get_department_domain(user)
    
    query = db.query(Job)
    
    if domain != "*":
        query = query.filter(Job.owner_domain == domain)
    
    if status_filter:
        query = query.filter(Job.status == status_filter)
    
    jobs = query.order_by(Job.created_at.desc()).all()
    
    # Get owner info for each job
    job_ids = [j.id for j in jobs]
    owners = {}
    if job_ids:
        owner_users = db.query(User).filter(User.id.in_([j.owner_id for j in jobs])).all()
        owners = {u.id: u.name for u in owner_users}
    
    return {
        "items": [
            {
                "id": j.id,
                "name": j.name,
                "type": j.type,
                "connector": j.connector,
                "owner_id": j.owner_id,
                "owner_name": owners.get(j.owner_id, "Unknown"),
                "owner_domain": j.owner_domain,
                "environment": j.environment,
                "status": j.status,
                "data_sensitivity": j.data_sensitivity,
                "created_at": j.created_at,
                "updated_at": j.updated_at,
            }
            for j in jobs
        ],
        "count": len(jobs)
    }


@router.get("/jobs/high-risk", response_model=dict)
def list_high_risk_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List high-risk jobs (high data sensitivity) in the admin's department."""
    _require_admin(user)
    domain = _get_department_domain(user)
    
    query = db.query(Job).filter(Job.data_sensitivity == "high")
    
    if domain != "*":
        query = query.filter(Job.owner_domain == domain)
    
    jobs = query.order_by(Job.created_at.desc()).all()
    
    owners = {}
    if jobs:
        owner_users = db.query(User).filter(User.id.in_([j.owner_id for j in jobs])).all()
        owners = {u.id: u.name for u in owner_users}
    
    return {
        "items": [
            {
                "id": j.id,
                "name": j.name,
                "type": j.type,
                "connector": j.connector,
                "owner_id": j.owner_id,
                "owner_name": owners.get(j.owner_id, "Unknown"),
                "owner_domain": j.owner_domain,
                "environment": j.environment,
                "status": j.status,
                "data_sensitivity": j.data_sensitivity,
                "created_at": j.created_at,
                "updated_at": j.updated_at,
            }
            for j in jobs
        ],
        "count": len(jobs)
    }


@router.get("/jobs/failed", response_model=dict)
def list_failed_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List failed jobs in the admin's department."""
    _require_admin(user)
    domain = _get_department_domain(user)
    
    query = db.query(Job).filter(Job.status == "failed")
    
    if domain != "*":
        query = query.filter(Job.owner_domain == domain)
    
    jobs = query.order_by(Job.created_at.desc()).all()
    
    owners = {}
    if jobs:
        owner_users = db.query(User).filter(User.id.in_([j.owner_id for j in jobs])).all()
        owners = {u.id: u.name for u in owner_users}
    
    return {
        "items": [
            {
                "id": j.id,
                "name": j.name,
                "type": j.type,
                "connector": j.connector,
                "owner_id": j.owner_id,
                "owner_name": owners.get(j.owner_id, "Unknown"),
                "owner_domain": j.owner_domain,
                "environment": j.environment,
                "status": j.status,
                "data_sensitivity": j.data_sensitivity,
                "created_at": j.created_at,
                "updated_at": j.updated_at,
            }
            for j in jobs
        ],
        "count": len(jobs)
    }


# ============================================================================
# RUNS ENDPOINTS
# ============================================================================

@router.get("/runs", response_model=dict)
def list_department_runs(
    status_filter: str = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List runs for jobs owned by users in the admin's department."""
    _require_admin(user)
    domain = _get_department_domain(user)
    
    # Get jobs in this domain first
    job_query = db.query(Job)
    if domain != "*":
        job_query = job_query.filter(Job.owner_domain == domain)
    
    job_ids = [j.id for j in job_query.all()]
    
    if not job_ids:
        return {"items": [], "count": 0}
    
    query = db.query(Run).filter(Run.job_id.in_(job_ids))
    
    if status_filter:
        query = query.filter(Run.status == status_filter)
    
    runs = query.order_by(Run.created_at.desc()).limit(limit).all()
    
    # Get job and user info
    jobs = {j.id: j for j in db.query(Job).filter(Job.id.in_([r.job_id for r in runs])).all()}
    users = {u.id: u for u in db.query(User).filter(User.id.in_([r.requested_by for r in runs])).all()}
    
    return {
        "items": [
            {
                "id": r.id,
                "job_id": r.job_id,
                "job_name": jobs.get(r.job_id, {}).name if jobs.get(r.job_id) else "Unknown",
                "requested_by": r.requested_by,
                "requested_by_name": users.get(r.requested_by, {}).name if users.get(r.requested_by) else "Unknown",
                "action": r.action,
                "status": r.status,
                "risk_level": r.risk_level,
                "risk_score": r.risk_score,
                "requires_approval": r.requires_approval,
                "target_environment": r.target_environment,
                "error": r.error,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in runs
        ],
        "count": len(runs)
    }


@router.get("/runs/failed", response_model=dict)
def list_failed_runs(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List failed runs for jobs in the admin's department."""
    _require_admin(user)
    domain = _get_department_domain(user)
    
    # Get jobs in this domain
    job_query = db.query(Job)
    if domain != "*":
        job_query = job_query.filter(Job.owner_domain == domain)
    
    job_ids = [j.id for j in job_query.all()]
    
    if not job_ids:
        return {"items": [], "count": 0}
    
    runs = (
        db.query(Run)
        .filter(Run.job_id.in_(job_ids), Run.status == "failed")
        .order_by(Run.created_at.desc())
        .limit(limit)
        .all()
    )
    
    # Get job and user info
    jobs = {j.id: j for j in db.query(Job).filter(Job.id.in_([r.job_id for r in runs])).all()}
    users = {u.id: u for u in db.query(User).filter(User.id.in_([r.requested_by for r in runs])).all()}
    
    return {
        "items": [
            {
                "id": r.id,
                "job_id": r.job_id,
                "job_name": jobs.get(r.job_id, {}).name if jobs.get(r.job_id) else "Unknown",
                "requested_by_name": users.get(r.requested_by, {}).name if users.get(r.requested_by) else "Unknown",
                "action": r.action,
                "status": r.status,
                "risk_level": r.risk_level,
                "error": r.error,
                "created_at": r.created_at,
            }
            for r in runs
        ],
        "count": len(runs)
    }


# ============================================================================
# APPROVAL REQUESTS ENDPOINTS
# ============================================================================

@router.get("/approvals", response_model=dict)
def list_pending_approvals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List pending approval requests in the admin's department."""
    _require_admin(user)
    domain = _get_department_domain(user)
    
    # Get jobs in this domain to filter runs
    job_query = db.query(Job)
    if domain != "*":
        job_query = job_query.filter(Job.owner_domain == domain)
    
    job_ids = [j.id for j in job_query.all()]
    
    if not job_ids:
        return {"items": [], "count": 0}
    
    # Get runs in this domain that need approval
    runs_needing_approval = db.query(Run).filter(
        Run.job_id.in_(job_ids),
        Run.requires_approval.is_(True),
        Run.status.in_(["pending_approval", "waiting"])
    ).all()
    
    approval_ids = [r.approval_id for r in runs_needing_approval if r.approval_id]
    
    if not approval_ids:
        return {"items": [], "count": 0}
    
    approvals = db.query(Approval).filter(Approval.id.in_(approval_ids)).all()
    
    # Get run, job, and user info
    run_map = {r.id: r for r in runs_needing_approval}
    jobs = {j.id: j for j in db.query(Job).filter(Job.id.in_([r.job_id for r in runs_needing_approval])).all()}
    users_set = set([a.requested_by for a in approvals] + [r.requested_by for r in runs_needing_approval])
    users = {u.id: u for u in db.query(User).filter(User.id.in_(users_set)).all()}
    
    return {
        "items": [
            {
                "id": a.id,
                "run_id": next((r.id for r in run_map.values() if r.approval_id == a.id), None),
                "job_id": next((r.job_id for r in run_map.values() if r.approval_id == a.id), None),
                "job_name": jobs.get(next((r.job_id for r in run_map.values() if r.approval_id == a.id), None), {}).name if next((r.job_id for r in run_map.values() if r.approval_id == a.id), None) else "Unknown",
                "status": a.status,
                "risk_level": a.risk_level,
                "requested_by": a.requested_by,
                "requested_by_name": users.get(a.requested_by, {}).name if users.get(a.requested_by) else "Unknown",
                "created_at": a.created_at,
                "comment": a.comment,
            }
            for a in approvals
        ],
        "count": len(approvals)
    }


@router.patch("/approvals/{approval_id}/approve", response_model=dict)
def approve_promotion(
    approval_id: str,
    comment: str = Query("", alias="comment"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Approve a promotion request."""
    _require_admin(user)
    domain = _get_department_domain(user)
    
    approval = db.query(Approval).filter(Approval.id == approval_id).one_or_none()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    
    # Verify admin can approve (approval should be in their department)
    run = db.query(Run).filter(Run.approval_id == approval_id).one_or_none()
    if run:
        job = db.query(Job).filter(Job.id == run.job_id).one_or_none()
        if job and domain != "*" and job.owner_domain != domain:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot approve promotions outside your department"
            )
    
    approval.status = "approved"
    approval.reviewer_id = user.id
    approval.reviewed_at = now_iso()
    if comment:
        approval.comment = comment
    
    db.commit()
    db.refresh(approval)
    
    return {
        "id": approval.id,
        "status": approval.status,
        "reviewer_id": approval.reviewer_id,
        "reviewed_at": approval.reviewed_at,
        "comment": approval.comment,
    }


@router.patch("/approvals/{approval_id}/reject", response_model=dict)
def reject_promotion(
    approval_id: str,
    comment: str = Query("", alias="comment"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Reject a promotion request."""
    _require_admin(user)
    domain = _get_department_domain(user)
    
    approval = db.query(Approval).filter(Approval.id == approval_id).one_or_none()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    
    # Verify admin can reject (approval should be in their department)
    run = db.query(Run).filter(Run.approval_id == approval_id).one_or_none()
    if run:
        job = db.query(Job).filter(Job.id == run.job_id).one_or_none()
        if job and domain != "*" and job.owner_domain != domain:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot reject promotions outside your department"
            )
    
    approval.status = "rejected"
    approval.reviewer_id = user.id
    approval.reviewed_at = now_iso()
    if comment:
        approval.comment = comment
    
    db.commit()
    db.refresh(approval)
    
    return {
        "id": approval.id,
        "status": approval.status,
        "reviewer_id": approval.reviewer_id,
        "reviewed_at": approval.reviewed_at,
        "comment": approval.comment,
    }

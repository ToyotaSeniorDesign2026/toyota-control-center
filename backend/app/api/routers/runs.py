from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_db
from app.schemas.run import PromotionStatusOut, RunCreate, RunOut
from app.services.run_service import (
    create_run_and_maybe_execute,
    get_run,
    get_run_promotion_status,
    list_runs,
    promote_run,
    retry_run,
    stop_run,
)

router = APIRouter()


@router.post("", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, db=Depends(get_db), user=Depends(get_current_user)):
    return create_run_and_maybe_execute(db, user, payload)


@router.get("/{run_id}", response_model=RunOut)
def read_run(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_run(db, user, run_id)


@router.get("", response_model=list[RunOut])
def read_runs(limit: int = Query(default=200, ge=1, le=1000), db=Depends(get_db), user=Depends(get_current_user)):
    return list_runs(db, user)[:limit]


@router.post("/{run_id}/promote", response_model=RunOut)
def promote(
    run_id: str,
    target_environment: str = Query(...),
    git_ref: str | None = Query(default=None),
    pr_number: int | None = Query(default=None),
    commit_sha: str | None = Query(default=None),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return promote_run(db, user, run_id, target_environment, git_ref=git_ref, pr_number=pr_number, commit_sha=commit_sha)


@router.get("/{run_id}/promotion-status", response_model=PromotionStatusOut)
def promotion_status(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_run_promotion_status(db, user, run_id)


@router.post("/{run_id}/stop", response_model=RunOut)
def stop(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return stop_run(db, user, run_id)


@router.post("/{run_id}/retry", response_model=RunOut)
def retry(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return retry_run(db, user, run_id)

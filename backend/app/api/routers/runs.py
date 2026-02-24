from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_db
from app.schemas.run import RunListOut, RunLogsOut, RunOut, RunStatusOut
from app.services.log_service import get_run_logs, get_run_status
from app.services.run_service import (
    get_run,
    query_runs,
    retry_run,
    stop_run,
)

router = APIRouter()


@router.get("/{run_id}", response_model=RunOut)
def read_run(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_run(db, user, run_id)


@router.get("", response_model=RunListOut)
def read_runs(
    resource_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    updated_since: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    cursor: str | None = Query(default=None),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return query_runs(
        db,
        user,
        resource_id=resource_id,
        status=status,
        updated_since=updated_since,
        limit=limit,
        cursor=cursor,
    )


@router.get("/{run_id}/status", response_model=RunStatusOut)
def read_status(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_run_status(db, user, run_id)


@router.get("/{run_id}/logs", response_model=RunLogsOut)
def read_logs(
    run_id: str,
    limit: int = Query(default=500, ge=1, le=5000),
    cursor: str | None = Query(default=None),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return get_run_logs(db, user, run_id=run_id, limit=limit, cursor=cursor)


@router.post("/{run_id}/cancel", response_model=RunOut)
def cancel(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return stop_run(db, user, run_id)


@router.post("/{run_id}/retry", response_model=RunOut)
def retry(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return retry_run(db, user, run_id)

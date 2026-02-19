from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_db
from app.schemas.run import RunLogsOut, RunStatusOut
from app.services.log_service import get_run_logs, get_run_status

router = APIRouter()


@router.get("/runs/{run_id}", response_model=RunLogsOut)
def read_run_logs(
    run_id: str,
    limit: int = Query(default=500, ge=1, le=5000),
    cursor: str | None = Query(default=None),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return get_run_logs(db, user, run_id=run_id, limit=limit, cursor=cursor)


@router.get("/runs/{run_id}/status", response_model=RunStatusOut)
def read_run_status(run_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    return get_run_status(db, user, run_id=run_id)

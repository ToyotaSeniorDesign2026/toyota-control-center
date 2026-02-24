from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.audit_event import RunLog
from app.models.run import Run


def append_run_log(db: Session, run_id: str, level: str, message: str, metadata: dict | None = None):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    row = RunLog(
        id=new_id("log"),
        run_id=run_id,
        timestamp=now_iso(),
        level=level,
        message=message,
        metadata_json=metadata or {},
    )
    db.add(row)
    db.commit()


def _can_access(user, run: Run) -> bool:
    return user.role == "root" or user.domain == run.domain or user.id == run.requested_by


def get_run_logs(db: Session, user, run_id: str, limit: int = 500, cursor: str | None = None):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not _can_access(user, run):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    rows = (
        db.query(RunLog)
        .filter(RunLog.run_id == run_id)
        .order_by(RunLog.timestamp.asc(), RunLog.id.asc())
        .all()
    )
    logs = [
        {
            "run_id": row.run_id,
            "timestamp": row.timestamp,
            "level": row.level,
            "message": row.message,
            "metadata": row.metadata_json or {},
        }
        for row in rows
    ]

    start = int(cursor) if cursor is not None else 0
    sliced = logs[start : start + limit]
    next_cursor = str(start + len(sliced)) if start + len(sliced) < len(logs) else None

    return {
        "run_id": run_id,
        "status": run.status,
        "logs": sliced,
        "next_cursor": next_cursor,
    }


def get_run_status(db: Session, user, run_id: str):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not _can_access(user, run):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    return {
        "run_id": run_id,
        "status": run.status,
        "risk_level": run.risk_level,
        "requires_approval": run.requires_approval,
        "updated_at": run.updated_at,
    }

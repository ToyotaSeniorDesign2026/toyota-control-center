from __future__ import annotations

"""Run logging/polling service: append logs, fetch run status/logs, and build event payloads."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.audit_event import RunLog
from app.models.run import Run, RunExecutionStatus


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
    touch_run_execution_status_from_log(db, run_id, row.timestamp)


def sync_run_execution_status(db: Session, run: Run):
    snapshot = db.get(RunExecutionStatus, run.id)
    if not snapshot:
        snapshot = RunExecutionStatus(
            run_id=run.id,
            status=run.status,
            risk_level=run.risk_level,
            requires_approval=run.requires_approval,
            updated_at=run.updated_at,
            last_log_at=None,
            log_count=0,
        )
    else:
        snapshot.status = run.status
        snapshot.risk_level = run.risk_level
        snapshot.requires_approval = run.requires_approval
        snapshot.updated_at = run.updated_at
    db.add(snapshot)
    db.commit()


def touch_run_execution_status_from_log(db: Session, run_id: str, log_ts: str | None = None):
    run = db.get(Run, run_id)
    if not run:
        return
    snapshot = db.get(RunExecutionStatus, run_id)
    if not snapshot:
        snapshot = RunExecutionStatus(
            run_id=run.id,
            status=run.status,
            risk_level=run.risk_level,
            requires_approval=run.requires_approval,
            updated_at=run.updated_at,
            last_log_at=log_ts or now_iso(),
            log_count=1,
        )
    else:
        snapshot.last_log_at = log_ts or now_iso()
        snapshot.log_count = int(snapshot.log_count or 0) + 1
    db.add(snapshot)
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
        "status": _effective_status(db, run).get("status"),
        "logs": sliced,
        "next_cursor": next_cursor,
    }


def get_run_status(db: Session, user, run_id: str):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not _can_access(user, run):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    status_payload = _effective_status(db, run)
    return {
        "run_id": run_id,
        "status": status_payload["status"],
        "risk_level": status_payload["risk_level"],
        "requires_approval": status_payload["requires_approval"],
        "updated_at": status_payload["updated_at"],
    }


def get_run_events(db: Session, user, run_id: str, cursor: str | None = None, limit: int = 200):
    status_evt = get_run_status(db, user, run_id)
    logs_out = get_run_logs(db, user, run_id, limit=limit, cursor=cursor)
    events = [{"event": "run.status", "data": status_evt}]
    events.extend({"event": "run.log", "data": log} for log in logs_out["logs"])
    return {
        "events": events,
        "next_cursor": logs_out["next_cursor"],
    }


def purge_run_logs(db: Session, user, run_id: str):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not _can_access(user, run):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    deleted = db.query(RunLog).filter(RunLog.run_id == run_id).delete(synchronize_session=False)
    snapshot = db.get(RunExecutionStatus, run_id)
    if snapshot:
        snapshot.log_count = 0
        snapshot.last_log_at = None
        db.add(snapshot)
    db.commit()
    return {"run_id": run_id, "deleted_logs": deleted}


def _effective_status(db: Session, run: Run) -> dict:
    snapshot = db.get(RunExecutionStatus, run.id)
    if snapshot:
        return {
            "status": snapshot.status,
            "risk_level": snapshot.risk_level,
            "requires_approval": snapshot.requires_approval,
            "updated_at": snapshot.updated_at,
        }
    return {
        "status": run.status,
        "risk_level": run.risk_level,
        "requires_approval": run.requires_approval,
        "updated_at": run.updated_at,
    }

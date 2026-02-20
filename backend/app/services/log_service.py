from __future__ import annotations

from fastapi import HTTPException, status

from app.core.db import now_iso


def append_run_log(db, run_id: str, level: str, message: str, metadata: dict | None = None):
    if run_id not in db.runs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    db.run_logs.setdefault(run_id, []).append(
        {
            "run_id": run_id,
            "timestamp": now_iso(),
            "level": level,
            "message": message,
            "metadata": metadata or {},
        }
    )


def get_run_logs(db, user, run_id: str, limit: int = 500, cursor: str | None = None):
    run = db.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    if user.role != "root" and user.domain != run["domain"] and user.id != run["requested_by"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    logs = db.run_logs.get(run_id, [])
    start = int(cursor) if cursor is not None else 0
    sliced = logs[start : start + limit]
    next_cursor = str(start + len(sliced)) if start + len(sliced) < len(logs) else None

    return {
        "run_id": run_id,
        "status": run["status"],
        "logs": sliced,
        "next_cursor": next_cursor,
    }


def get_run_status(db, user, run_id: str):
    run = db.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    if user.role != "root" and user.domain != run["domain"] and user.id != run["requested_by"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    return {
        "run_id": run_id,
        "status": run["status"],
        "risk_level": run["risk_level"],
        "requires_approval": run["requires_approval"],
        "updated_at": run["updated_at"],
    }

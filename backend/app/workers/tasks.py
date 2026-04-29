from __future__ import annotations

import asyncio
from contextlib import suppress

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.scheduler_service import run_due_scheduled_jobs


# Worker task placeholders for asynchronous orchestration.
# In production this would call Celery/RQ tasks and stream connector logs.


def enqueue_run(run_id: str) -> dict:
    return {"run_id": run_id, "status": "queued"}


async def scheduler_loop(stop_event: asyncio.Event | None = None) -> None:
    if not settings.job_scheduler_enabled:
        return

    interval = max(5, settings.job_scheduler_interval_seconds)
    while stop_event is None or not stop_event.is_set():
        db = SessionLocal()
        try:
            run_due_scheduled_jobs(db)
        finally:
            db.close()

        with suppress(asyncio.TimeoutError):
            if stop_event is None:
                await asyncio.sleep(interval)
            else:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)

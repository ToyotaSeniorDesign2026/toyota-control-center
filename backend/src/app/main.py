"""FastAPI app entrypoint and router wiring for the control-plane API."""

import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

_logger = logging.getLogger(__name__)

from app.api.routers import audit, auth, chat, connectors, integrations, job_types, jobs, policy, runs
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.workers.tasks import scheduler_loop
from app.services.run_service import cleanup_orphaned_runs


def create_app() -> FastAPI:
    setup_logging()
    init_db()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        _logger.error("Request validation error on %s %s: %s", request.method, request.url.path, exc.errors())
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AuditMiddleware)

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(job_types.router, prefix="/job-types", tags=["job-types"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs-registry"])
    app.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
    app.include_router(runs.router, prefix="/runs", tags=["run-orchestration"])

    app.include_router(policy.router, prefix="/policy", tags=["policy"])
    app.include_router(audit.router, prefix="/audit", tags=["audit"])
    app.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

    scheduler_stop_event: asyncio.Event | None = None
    scheduler_task: asyncio.Task | None = None

    @app.on_event("startup")
    async def start_scheduler() -> None:
        nonlocal scheduler_stop_event, scheduler_task
        from app.api.deps import get_db
        db = next(get_db())
        try:
            cleanup_orphaned_runs(db)
        except Exception:
            _logger.exception("Failed to clean up orphaned runs on startup")
        finally:
            db.close()
        if not settings.job_scheduler_enabled:
            return
        scheduler_stop_event = asyncio.Event()
        scheduler_task = asyncio.create_task(scheduler_loop(scheduler_stop_event))

    @app.on_event("shutdown")
    async def stop_scheduler() -> None:
        if scheduler_stop_event is not None:
            scheduler_stop_event.set()
        if scheduler_task is not None:
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass

    return app


app = create_app()

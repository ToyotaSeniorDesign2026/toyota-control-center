"""FastAPI app entrypoint and router wiring for the control-plane API."""

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import audit, auth, chat, integrations, policy, resource_types, resources, runs
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.workers.tasks import scheduler_loop


def create_app() -> FastAPI:
    setup_logging()
    init_db()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

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
    app.include_router(resource_types.router, prefix="/resource-types", tags=["resource-types"])
    app.include_router(resources.router, prefix="/resources", tags=["resources-registry"])
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

"""FastAPI app entrypoint and router wiring for the control-plane API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import audit, auth, integrations, policy, resource_types, resources, runs
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.request_id import RequestIdMiddleware


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

    return app


app = create_app()

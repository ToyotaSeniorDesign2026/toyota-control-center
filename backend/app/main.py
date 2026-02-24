from fastapi import FastAPI

from app.api.routers import audit, auth, integrations, policy, resources, runs
from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.request_id import RequestIdMiddleware


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AuditMiddleware)

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(resources.router, prefix="/resources", tags=["resources-registry"])
    app.include_router(runs.router, prefix="/runs", tags=["run-orchestration"])

    app.include_router(policy.router, prefix="/policy", tags=["policy"])
    app.include_router(audit.router, prefix="/audit", tags=["audit"])
    app.include_router(integrations.router, prefix="/integrations", tags=["integrations"])

    return app


app = create_app()

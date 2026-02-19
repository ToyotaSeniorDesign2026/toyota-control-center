from starlette.middleware.base import BaseHTTPMiddleware

from app.core.audit import emit_audit_event


_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method in _MUTATING_METHODS:
            actor = None
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                actor = auth_header.split(" ", 1)[1].strip()
            emit_audit_event(
                actor_id=actor,
                action="HTTP_MUTATION",
                metadata={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "request_id": getattr(request.state, "request_id", None),
                },
            )
        return response

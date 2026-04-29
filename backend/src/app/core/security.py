from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.models.user import User
from app.schemas.user import UserOut


bearer = HTTPBearer(auto_error=False)

_SERVICE_USER = UserOut(
    id="cc-service",
    email="service@control-center.internal",
    name="Control Center Service",
    role="root",
    domain="internal",
    is_active=True,
    created_at="",
)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db_session),
):
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = creds.credentials.strip()

    # Allow the internal service token (used by the Control Center MCP server)
    from app.core.config import settings
    if settings.internal_service_token and token == settings.internal_service_token:
        return _SERVICE_USER

    user = db.get(User, token)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return UserOut.model_validate(user, from_attributes=True)

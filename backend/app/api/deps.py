from fastapi import Depends

from app.core.database import get_db_session
from app.core.rbac import require_role
from app.core.security import get_current_user


def get_db():
    yield from get_db_session()


def require_root(user=Depends(get_current_user)):
    return require_role(["root"])(user)


def require_domain_admin(user=Depends(get_current_user)):
    return require_role(["root", "domain_admin"])(user)


def require_any_user(user=Depends(get_current_user)):
    return require_role(["root", "domain_admin", "user"])(user)

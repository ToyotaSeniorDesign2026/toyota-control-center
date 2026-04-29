from fastapi import HTTPException, status


ALLOWED_ROLES = {"root", "domain_admin", "user"}


def require_role(allowed: list[str]):
    invalid = [role for role in allowed if role not in ALLOWED_ROLES]
    if invalid:
        raise ValueError(f"Unknown roles in RBAC config: {invalid}")

    def _check(user):
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check

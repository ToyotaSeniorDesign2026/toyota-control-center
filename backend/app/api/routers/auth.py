from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.db import get_db
from app.schemas.user import LoginRequest, TokenOut, UserOut

router = APIRouter()


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest):
    db = get_db()
    user = next((u for u in db.users.values() if u["email"] == payload.email), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {
        "access_token": user["id"],
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user

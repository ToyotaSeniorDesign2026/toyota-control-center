from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import LoginRequest, TokenOut, UserOut, UserUpdateRequest

router = APIRouter()


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {
        "access_token": user.id,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(payload: UserUpdateRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if payload.name is not None:
        user.name = payload.name.strip() or user.name
    if payload.email is not None:
        normalized_email = payload.email.strip().lower()
        existing = db.query(User).filter(User.email == normalized_email, User.id != user.id).one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        user.email = normalized_email

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

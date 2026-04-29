from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import LoginRequest, TokenOut, UserOut, UserUpdate

router = APIRouter()


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {
        "access_token": user.id,
        "token_type": "bearer",
        "user": user,  # User object includes role, domain, and name
    }


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserOut)
def update_me(payload: UserUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Update current user's profile and preferences.
    
    Users can only update:
    - first_name, last_name
    - phone, location, bio
    - avatar_type, uploaded_image, selected_color
    - theme, notifications, timezone
    
    Fields that cannot be changed by users:
    - email, role, domain
    - mfa_enabled, approval_authority, allowed_environments
    - access_token, password_last_changed
    """
    # Refresh user from database in this session
    user = db.query(User).filter(User.id == user.id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    # Update profile fields if provided
    if payload.first_name is not None:
        user.first_name = payload.first_name
    if payload.last_name is not None:
        user.last_name = payload.last_name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.location is not None:
        user.location = payload.location
    if payload.bio is not None:
        user.bio = payload.bio
    
    # Update avatar fields if provided
    if payload.avatar_type is not None:
        user.avatar_type = payload.avatar_type
    if payload.uploaded_image is not None:
        user.uploaded_image = payload.uploaded_image
    if payload.selected_color is not None:
        user.selected_color = payload.selected_color
    
    # Update preferences if provided
    if payload.theme is not None:
        user.theme = payload.theme
    if payload.notifications is not None:
        user.notifications = payload.notifications
    if payload.timezone is not None:
        user.timezone = payload.timezone
    
    # Commit changes to database
    db.commit()
    db.refresh(user)
    
    return user

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Core identity (read-only)
    id: str
    email: EmailStr
    name: str
    role: str
    domain: str
    is_active: bool = True
    created_at: str

    # Profile fields
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    location: str | None = None
    bio: str | None = None

    # Profile customization
    avatar_type: str | None = None
    uploaded_image: str | None = None
    selected_color: str | None = None

    # Security & Access (read-only for users)
    mfa_enabled: bool | None = None
    approval_authority: bool | None = None
    allowed_environments: str | None = None
    password_last_changed: datetime | None = None
    access_token: str | None = None
    cli_token: str | None = None

    # User preferences
    theme: str | None = None
    notifications: str | None = None
    timezone: str | None = None

    # Organization & Team Information (read-only, managed by HR)
    job_title: str | None = None
    department: str | None = None
    team: str | None = None
    manager: str | None = None
    employee_id: str | None = None


class UserUpdate(BaseModel):
    """Schema for updating user profile and preferences.
    Only fields that users are allowed to update are included.
    """
    # Profile fields (editable)
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    location: str | None = None
    bio: str | None = None

    # Avatar customization (editable)
    avatar_type: str | None = None
    uploaded_image: str | None = None
    selected_color: str | None = None

    # Preferences (editable)
    theme: str | None = None
    notifications: str | None = None
    timezone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

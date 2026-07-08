from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str | None = Field(default=None, max_length=200)
    code: str = Field(min_length=4, max_length=10)


class RequestCodeRequest(BaseModel):
    email: EmailStr
    purpose: str = "register"


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str | None = None
    avatar_url: str | None = None
    is_platform_admin: bool
    created_at: datetime


class WhoamiOut(BaseModel):
    type: str
    user_id: UUID | None = None
    email: str | None = None
    token_id: UUID | None = None
    token_name: str | None = None
    workspace_id: UUID | None = None
    scopes: list[str] = Field(default_factory=list)

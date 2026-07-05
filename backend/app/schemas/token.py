from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TokenCreate(BaseModel):
    workspace_slug: str
    name: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(default_factory=list)
    project_allowlist: list[str] | None = None
    expires_at: datetime | None = None


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    token_prefix: str
    scopes: list[str]
    project_allowlist: list[str] | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class TokenCreateResponse(BaseModel):
    token: str
    token_prefix: str
    warning: str = "This token is shown only once. Store it securely."
    token_info: TokenOut

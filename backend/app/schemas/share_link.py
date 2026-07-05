from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ShareLinkCreate(BaseModel):
    access_type: str = "latest"
    version: int | None = None
    password: str | None = None
    expires_at: datetime | None = None
    max_views: int | None = None


class ShareLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    version_id: UUID | None = None
    access_type: str
    has_password: bool = False
    expires_at: datetime | None = None
    max_views: int | None = None
    view_count: int
    revoked_at: datetime | None = None
    created_at: datetime


class ShareLinkCreateResponse(BaseModel):
    share_url: str
    access_type: str
    expires_at: datetime | None = None
    link: ShareLinkOut


class SharePasswordVerify(BaseModel):
    password: str

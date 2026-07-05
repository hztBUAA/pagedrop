from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    type: str
    owner_user_id: UUID
    created_at: datetime


class WorkspaceWithRole(WorkspaceOut):
    role: str = ""


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    workspace_id: UUID
    role: str
    created_at: datetime


class MemberAdd(BaseModel):
    email: str
    role: str = "viewer"


class MemberUpdate(BaseModel):
    role: str

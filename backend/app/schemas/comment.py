from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)
    thread_root_id: UUID | None = None
    anchor_version_number: int | None = None
    anchor_quote: str | None = Field(default=None, max_length=4000)
    anchor_prefix: str | None = Field(default=None, max_length=200)
    anchor_suffix: str | None = Field(default=None, max_length=200)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    thread_root_id: UUID | None = None
    anchor_version_number: int | None = None
    anchor_quote: str | None = None
    anchor_prefix: str | None = None
    anchor_suffix: str | None = None
    body: str
    status: str
    author_source: str
    author_display: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

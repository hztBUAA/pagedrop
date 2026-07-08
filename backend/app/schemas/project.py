from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import CONTENT_TYPES, VISIBILITIES


class PublishRequest(BaseModel):
    workspace_slug: str
    slug: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    content_type: str = "markdown"
    content: str
    visibility: str = "private"
    message: str | None = None
    summary: str | None = None
    source: str = "web"
    force: bool = False

    def validate_enums(self) -> str | None:
        if self.content_type not in CONTENT_TYPES:
            return "invalid_content_type"
        if self.visibility not in VISIBILITIES:
            return "invalid_visibility"
        return None


class PublishResponse(BaseModel):
    project_id: UUID
    version_id: UUID
    slug: str
    version: int
    latest_url: str
    version_url: str
    visibility: str
    secret_scan_status: str


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    slug: str
    title: str
    description: str | None = None
    default_content_type: str
    visibility: str
    latest_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    version_number: int
    content_type: str
    source_content: str
    rendered_html: str | None = None
    title: str
    summary: str | None = None
    changelog: str | None = None
    created_by_source: str
    secret_scan_status: str
    created_at: datetime


class VersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    title: str
    content_type: str
    changelog: str | None = None
    created_by_source: str
    created_at: datetime


class ProjectSettingsUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    visibility: str | None = None

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PublicPage(BaseModel):
    workspace_slug: str
    project_slug: str
    project_id: UUID
    title: str
    visibility: str
    content_type: str
    source_content: str
    rendered_html: str | None = None
    version_number: int
    summary: str | None = None
    is_latest: bool
    noindex: bool
    updated_at: datetime

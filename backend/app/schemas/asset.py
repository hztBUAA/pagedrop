from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    project_id: UUID | None = None
    sha256: str
    content_type: str
    byte_size: int
    width: int | None = None
    height: int | None = None
    original_name: str | None = None
    created_at: datetime


class AssetCreateResponse(AssetOut):
    # Stable reference to embed in Markdown/HTML, e.g. ![](pagedrop://asset/<id>)
    ref: str

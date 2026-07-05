import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID, JSONType
from app.models.base import UUIDMixin, utcnow

# Token scopes
SCOPE_PROJECTS_READ = "projects:read"
SCOPE_PROJECTS_WRITE = "projects:write"
SCOPE_VERSIONS_READ = "versions:read"
SCOPE_VERSIONS_WRITE = "versions:write"
SCOPE_ASSETS_WRITE = "assets:write"
SCOPE_SHARE_LINKS_CREATE = "share_links:create"
SCOPE_TOKENS_READ = "tokens:read"
VALID_SCOPES = {
    SCOPE_PROJECTS_READ,
    SCOPE_PROJECTS_WRITE,
    SCOPE_VERSIONS_READ,
    SCOPE_VERSIONS_WRITE,
    SCOPE_ASSETS_WRITE,
    SCOPE_SHARE_LINKS_CREATE,
    SCOPE_TOKENS_READ,
}


class ApiToken(UUIDMixin, Base):
    __tablename__ = "api_tokens"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    scopes: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    project_allowlist: Mapped[list | None] = mapped_column(JSONType)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_ip: Mapped[str | None] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

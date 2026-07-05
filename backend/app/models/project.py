import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID
from app.models.base import TimestampMixin, UUIDMixin

# Content types
CONTENT_MARKDOWN = "markdown"
CONTENT_SAFE_HTML = "safe_html"
CONTENT_SANDBOX_HTML = "sandbox_html"
CONTENT_TYPES = {CONTENT_MARKDOWN, CONTENT_SAFE_HTML, CONTENT_SANDBOX_HTML}

# Visibility
VISIBILITY_PUBLIC = "public"
VISIBILITY_UNLISTED = "unlisted"
VISIBILITY_PRIVATE = "private"
VISIBILITIES = {VISIBILITY_PUBLIC, VISIBILITY_UNLISTED, VISIBILITY_PRIVATE}


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_workspace_slug"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_content_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CONTENT_MARKDOWN
    )
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default=VISIBILITY_UNLISTED)
    latest_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), nullable=False
    )

    workspace = relationship("Workspace")
    versions = relationship(
        "PageVersion",
        back_populates="project",
        cascade="all, delete-orphan",
        foreign_keys="PageVersion.project_id",
    )

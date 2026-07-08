import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID
from app.models.base import UUIDMixin, utcnow

ALLOWED_IMAGE_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


class Asset(UUIDMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "sha256", name="uq_workspace_asset_sha256"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    # Nullable: assets are normally bound to a project but may be workspace-scoped.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("projects.id"), index=True
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(400), nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(300))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    created_by_token_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    created_by_source: Mapped[str] = mapped_column(String(20), nullable=False, default="web")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

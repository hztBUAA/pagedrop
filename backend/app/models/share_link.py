import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID
from app.models.base import UUIDMixin, utcnow

# access_type
ACCESS_LATEST = "latest"
ACCESS_FIXED_VERSION = "fixed_version"


class ShareLink(UUIDMixin, Base):
    __tablename__ = "share_links"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("projects.id"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("page_versions.id"))
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    access_type: Mapped[str] = mapped_column(String(20), nullable=False, default=ACCESS_LATEST)
    password_hash: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_views: Mapped[int | None] = mapped_column(Integer)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

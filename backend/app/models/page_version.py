import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID
from app.models.base import UUIDMixin, utcnow

# created_by_source
SOURCE_WEB = "web"
SOURCE_CLI = "cli"
SOURCE_API = "api"
SOURCE_AGENT = "agent"
SOURCES = {SOURCE_WEB, SOURCE_CLI, SOURCE_API, SOURCE_AGENT}

# secret_scan_status
SCAN_PASSED = "passed"
SCAN_BLOCKED = "blocked"
SCAN_OVERRIDDEN = "overridden"


class PageVersion(UUIDMixin, Base):
    __tablename__ = "page_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_version"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("projects.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_content: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    changelog: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"))
    created_by_token_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    created_by_source: Mapped[str] = mapped_column(String(20), nullable=False, default=SOURCE_WEB)
    secret_scan_status: Mapped[str] = mapped_column(String(20), nullable=False, default=SCAN_PASSED)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    project = relationship("Project", back_populates="versions", foreign_keys=[project_id])

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID
from app.models.base import UUIDMixin, utcnow

STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"
STATUSES = {STATUS_OPEN, STATUS_RESOLVED}


class Comment(UUIDMixin, Base):
    __tablename__ = "comments"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("projects.id"), nullable=False, index=True
    )
    # Null for a top-level comment; set to a top-level comment id for a reply.
    thread_root_id: Mapped[uuid.UUID | None] = mapped_column(GUID, index=True)
    # Which version the comment was anchored against (for context / drift detection).
    anchor_version_number: Mapped[int | None] = mapped_column(Integer)
    # TextQuoteSelector: the selected text plus surrounding context, used to
    # re-locate the anchor across versions. Null for replies.
    anchor_quote: Mapped[str | None] = mapped_column(Text)
    anchor_prefix: Mapped[str | None] = mapped_column(String(200))
    anchor_suffix: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_OPEN)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    author_token_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    author_source: Mapped[str] = mapped_column(String(20), nullable=False, default="web")
    author_display: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID)

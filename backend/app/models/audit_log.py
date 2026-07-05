import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID, JSONType
from app.models.base import UUIDMixin, utcnow


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("workspaces.id"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"))
    token_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("api_tokens.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSONType)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

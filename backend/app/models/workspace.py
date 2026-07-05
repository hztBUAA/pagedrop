import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID
from app.models.base import TimestampMixin, UUIDMixin, utcnow

# Workspace types
WORKSPACE_PERSONAL = "personal"
WORKSPACE_TEAM = "team"

# Member roles (ordered by privilege)
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"
ROLE_ORDER = {ROLE_VIEWER: 0, ROLE_EDITOR: 1, ROLE_ADMIN: 2, ROLE_OWNER: 3}


class Workspace(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default=WORKSPACE_PERSONAL)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), nullable=False
    )

    members = relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceMember(UUIDMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workspaces.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_VIEWER)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="memberships")

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    # Nullable: OAuth-only accounts (e.g. GitHub/Google) have no local password.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    memberships = relationship("WorkspaceMember", back_populates="user")
    oauth_identities = relationship(
        "OAuthIdentity", back_populates="user", cascade="all, delete-orphan"
    )

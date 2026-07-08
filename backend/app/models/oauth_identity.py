from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID
from app.models.base import TimestampMixin, UUIDMixin


class OAuthIdentity(UUIDMixin, TimestampMixin, Base):
    """A third-party identity (GitHub, Google, ...) linked to a PageDrop user.

    Auth.js/NextAuth-style: one row per (provider, provider account), so a single
    user can link multiple providers over time.
    """

    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    )

    user_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_login: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    user = relationship("User", back_populates="oauth_identities")

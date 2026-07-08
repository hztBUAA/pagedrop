from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class VerificationCode(UUIDMixin, Base):
    __tablename__ = "verification_codes"

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

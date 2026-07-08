import secrets
from datetime import timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.base import utcnow
from app.models.verification_code import VerificationCode

MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _as_aware(dt):
    # SQLite round-trips tz-aware datetimes as naive; treat those as UTC.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _latest(db: Session, email: str, purpose: str) -> VerificationCode | None:
    return db.scalar(
        select(VerificationCode)
        .where(VerificationCode.email == email.lower(), VerificationCode.purpose == purpose)
        .order_by(VerificationCode.created_at.desc())
    )


def in_cooldown(db: Session, email: str, purpose: str) -> bool:
    latest = _latest(db, email, purpose)
    if latest is None:
        return False
    age = (utcnow() - _as_aware(latest.created_at)).total_seconds()
    return age < RESEND_COOLDOWN_SECONDS


def issue_code(db: Session, email: str, purpose: str) -> str:
    email = email.lower()
    now = utcnow()
    code = _generate_code()
    record = VerificationCode(
        email=email,
        purpose=purpose,
        code=code,
        expires_at=now + timedelta(seconds=settings.verification_code_ttl_seconds),
        used=False,
        attempts=0,
        created_at=now,
    )
    db.add(record)
    db.commit()
    return code


def verify_code(db: Session, email: str, code: str, purpose: str) -> bool:
    record = _latest(db, email, purpose)
    if record is None or record.used:
        return False
    if record.attempts >= MAX_ATTEMPTS:
        return False
    if record.expires_at is not None and _as_aware(record.expires_at) < utcnow():
        return False
    if record.code != code:
        record.attempts += 1
        db.commit()
        return False
    record.used = True
    db.commit()
    return True

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User


def _extract_session_token(request: Request) -> str | None:
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        return token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        candidate = auth[7:].strip()
        # API tokens (pd_*) are handled separately; only treat JWTs here.
        if not candidate.startswith("pd_"):
            return candidate
    return None


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = _extract_session_token(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    return db.get(User, sub)


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated"
        )
    return user

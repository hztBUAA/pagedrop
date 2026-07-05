import uuid
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import generate_token, hash_token
from app.models.api_token import VALID_SCOPES, ApiToken

TOKEN_PREFIX = "pd_live_"


class TokenError(Exception):
    pass


def create_token(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    scopes: list[str],
    project_allowlist: list[str] | None,
    expires_at: datetime | None,
) -> tuple[ApiToken, str]:
    invalid = set(scopes) - VALID_SCOPES
    if invalid:
        raise TokenError(f"invalid_scopes:{','.join(sorted(invalid))}")

    plaintext = generate_token(TOKEN_PREFIX)
    token = ApiToken(
        workspace_id=workspace_id,
        created_by_user_id=user_id,
        name=name,
        token_prefix=plaintext[: len(TOKEN_PREFIX) + 4],
        token_hash=hash_token(plaintext),
        scopes=scopes,
        project_allowlist=project_allowlist,
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, plaintext


def list_tokens(db: Session, workspace_id: uuid.UUID) -> list[ApiToken]:
    return list(
        db.scalars(
            select(ApiToken)
            .where(ApiToken.workspace_id == workspace_id)
            .order_by(ApiToken.created_at.desc())
        )
    )


def get_token(db: Session, token_id: uuid.UUID) -> ApiToken | None:
    return db.get(ApiToken, token_id)


def revoke(db: Session, token: ApiToken) -> None:
    if token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        db.commit()


def _is_active(token: ApiToken) -> bool:
    if token.revoked_at is not None:
        return False
    if token.expires_at is not None:
        exp = token.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return False
    return True


def authenticate(db: Session, raw_token: str, request: Request | None = None) -> ApiToken | None:
    token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(raw_token)))
    if token is None or not _is_active(token):
        return None
    token.last_used_at = datetime.now(timezone.utc)
    if request is not None and request.client:
        token.last_used_ip = request.client.host
    db.commit()
    return token

"""Unified actor resolution for endpoints usable by both humans and API tokens.

A session user has implicit full scopes within their workspaces; an API token
carries an explicit scope set and optional project allowlist (wired in Phase 7).
"""

from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_optional_user
from app.models.api_token import ApiToken
from app.models.user import User

FULL_SCOPES = {
    "projects:read",
    "projects:write",
    "versions:read",
    "versions:write",
    "assets:write",
    "share_links:create",
    "tokens:read",
}


@dataclass
class Actor:
    user: User | None = None
    token: ApiToken | None = None
    scopes: set[str] = field(default_factory=set)
    source: str = "web"

    @property
    def user_id(self):
        return self.user.id if self.user else None

    @property
    def token_id(self):
        return self.token.id if self.token else None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def require_scope(self, scope: str) -> None:
        if not self.has_scope(scope):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_scope")

    def token_allows_project(self, project_slug: str) -> bool:
        if self.token is None:
            return True
        allow = self.token.project_allowlist
        if not allow:
            return True
        return project_slug in allow


def _api_token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        candidate = auth[7:].strip()
        if candidate.startswith("pd_"):
            return candidate
    return None


def get_actor(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Actor:
    raw_token = _api_token_from_request(request)
    if raw_token:
        # Deferred import: token authentication is implemented in Phase 7.
        from app.services import token_service

        token = token_service.authenticate(db, raw_token, request)
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token"
            )
        return Actor(
            user=db.get(User, token.created_by_user_id),
            token=token,
            scopes=set(token.scopes or []),
            source="agent",
        )
    if user is not None:
        return Actor(user=user, token=None, scopes=set(FULL_SCOPES), source="web")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

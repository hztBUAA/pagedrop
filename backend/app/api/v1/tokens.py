import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.models.user import User
from app.permissions import service as perms
from app.schemas.token import TokenCreate, TokenCreateResponse, TokenOut
from app.services import audit_service, token_service, workspace_service

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("", response_model=list[TokenOut])
def list_tokens(
    workspace_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not perms.can_manage_tokens(db, user, workspace_id):
        raise HTTPException(status_code=403, detail="forbidden")
    return token_service.list_tokens(db, workspace_id)


@router.post(
    "",
    response_model=TokenCreateResponse,
    status_code=201,
    dependencies=[rate_limit("token_create", limit=10, window_seconds=60)],
)
def create_token(
    payload: TokenCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = workspace_service.get_workspace_by_slug(db, payload.workspace_slug)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace_not_found")
    if not perms.can_manage_tokens(db, user, workspace.id):
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        token, plaintext = token_service.create_token(
            db,
            workspace_id=workspace.id,
            user_id=user.id,
            name=payload.name,
            scopes=payload.scopes,
            project_allowlist=payload.project_allowlist,
            expires_at=payload.expires_at,
        )
    except token_service.TokenError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    audit_service.record(
        db,
        action="token.create",
        target_type="api_token",
        target_id=token.id,
        workspace_id=workspace.id,
        user_id=user.id,
        request=request,
    )
    return TokenCreateResponse(
        token=plaintext,
        token_prefix=token.token_prefix,
        token_info=TokenOut.model_validate(token),
    )


@router.delete("/{token_id}", status_code=200)
def revoke_token(
    token_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = token_service.get_token(db, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="token_not_found")
    if not perms.can_manage_tokens(db, user, token.workspace_id):
        raise HTTPException(status_code=403, detail="forbidden")
    token_service.revoke(db, token)
    audit_service.record(
        db,
        action="token.revoke",
        target_type="api_token",
        target_id=token.id,
        workspace_id=token.workspace_id,
        user_id=user.id,
        request=request,
    )
    return {"status": "revoked"}

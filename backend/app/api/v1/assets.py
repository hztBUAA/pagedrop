import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.actor import Actor, get_actor
from app.core.config import settings
from app.core.database import get_db
from app.core.ratelimit import rate_limit
from app.core.urls import asset_ref
from app.models.project import Project
from app.models.workspace import ROLE_EDITOR
from app.permissions import service as perms
from app.schemas.asset import AssetCreateResponse, AssetOut
from app.services import asset_service, audit_service, project_service, workspace_service

router = APIRouter(tags=["assets"])

_CACHE_IMMUTABLE = "public, max-age=31536000, immutable"


def _authorize_upload(db: Session, actor: Actor, workspace, project_slug: str | None) -> None:
    if actor.token is not None:
        actor.require_scope("assets:write")
        if actor.token.workspace_id != workspace.id:
            raise HTTPException(status_code=403, detail="token_workspace_mismatch")
        if project_slug and not actor.token_allows_project(project_slug):
            raise HTTPException(status_code=403, detail="project_not_in_allowlist")
        return
    if actor.user is not None and actor.user.is_platform_admin:
        return
    role = perms.get_role(db, actor.user_id, workspace.id) if actor.user_id else None
    if not perms.role_at_least(role, ROLE_EDITOR):
        raise HTTPException(status_code=403, detail="forbidden")


@router.post(
    "/assets",
    response_model=AssetCreateResponse,
    dependencies=[rate_limit("asset_upload", limit=60, window_seconds=60)],
)
async def upload_asset(
    request: Request,
    file: UploadFile = File(...),
    workspace_slug: str = Form(...),
    project_slug: str | None = Form(None),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    workspace = workspace_service.get_workspace_by_slug(db, workspace_slug)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace_not_found")
    _authorize_upload(db, actor, workspace, project_slug)

    project_id = None
    if project_slug:
        project = project_service.get_project(db, workspace.id, project_slug)
        project_id = project.id if project else None

    data = await file.read()
    try:
        asset = asset_service.create_asset(
            db,
            workspace_id=workspace.id,
            project_id=project_id,
            data=data,
            content_type=file.content_type or "application/octet-stream",
            original_name=file.filename,
            max_bytes=settings.asset_max_bytes,
            user_id=actor.user_id,
            token_id=actor.token_id,
            source=actor.source,
        )
    except asset_service.UnsupportedAssetTypeError:
        raise HTTPException(status_code=415, detail="unsupported_media_type") from None
    except asset_service.AssetTooLargeError:
        raise HTTPException(status_code=413, detail="asset_too_large") from None

    audit_service.record(
        db,
        action="asset.upload",
        target_type="asset",
        target_id=asset.id,
        workspace_id=workspace.id,
        user_id=actor.user_id,
        token_id=actor.token_id,
        request=request,
        metadata={"sha256": asset.sha256, "content_type": asset.content_type},
    )
    return AssetCreateResponse(
        **AssetOut.model_validate(asset).model_dump(), ref=asset_ref(asset.id)
    )


def _serve(asset) -> Response:
    return Response(
        content=asset_service.read_bytes(asset),
        media_type=asset.content_type,
        headers={"Cache-Control": _CACHE_IMMUTABLE},
    )


@router.get("/assets/{asset_id}")
def get_asset(
    asset_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    asset = asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset_not_found")
    if actor.token is not None:
        actor.require_scope("versions:read")
        if actor.token.workspace_id != asset.workspace_id:
            raise HTTPException(status_code=403, detail="token_workspace_mismatch")
        # Enforce the token's project allowlist. A workspace-scoped asset
        # (project_id NULL) is only reachable by tokens without an allowlist.
        if asset.project_id is not None:
            project = db.get(Project, asset.project_id)
            slug = project.slug if project is not None else None
            if slug is None or not actor.token_allows_project(slug):
                raise HTTPException(status_code=404, detail="not_found")
        elif actor.token.project_allowlist:
            raise HTTPException(status_code=404, detail="not_found")
        return _serve(asset)

    # Asset visibility follows its owning project; workspace-scoped assets
    # require membership.
    if asset.project_id is not None:
        project = db.get(Project, asset.project_id)
        if project is not None and not perms.can_view_project(db, actor.user, project):
            raise HTTPException(status_code=404, detail="not_found")
    else:
        is_admin = actor.user is not None and actor.user.is_platform_admin
        role = perms.get_role(db, actor.user_id, asset.workspace_id) if actor.user_id else None
        if role is None and not is_admin:
            raise HTTPException(status_code=404, detail="not_found")
    return _serve(asset)

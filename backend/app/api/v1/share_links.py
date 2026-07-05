import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.urls import share_url
from app.models.project import Project
from app.models.user import User
from app.permissions import service as perms
from app.schemas.share_link import (
    ShareLinkCreate,
    ShareLinkCreateResponse,
    ShareLinkOut,
)
from app.services import audit_service, project_service, share_link_service

router = APIRouter(tags=["share-links"])


def _to_out(link) -> ShareLinkOut:
    return ShareLinkOut(
        id=link.id,
        project_id=link.project_id,
        version_id=link.version_id,
        access_type=link.access_type,
        has_password=link.password_hash is not None,
        expires_at=link.expires_at,
        max_views=link.max_views,
        view_count=link.view_count,
        revoked_at=link.revoked_at,
        created_at=link.created_at,
    )


@router.get(
    "/projects/{workspace_slug}/{slug}/share-links", response_model=list[ShareLinkOut]
)
def list_share_links(
    workspace_slug: str,
    slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = project_service.get_project_by_slugs(db, workspace_slug, slug)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    if not perms.can_manage_project(db, user, project):
        raise HTTPException(status_code=403, detail="forbidden")
    return [_to_out(link) for link in share_link_service.list_for_project(db, project.id)]


@router.post(
    "/projects/{workspace_slug}/{slug}/share-links",
    response_model=ShareLinkCreateResponse,
    status_code=201,
)
def create_share_link(
    workspace_slug: str,
    slug: str,
    payload: ShareLinkCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = project_service.get_project_by_slugs(db, workspace_slug, slug)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    if not perms.can_create_share_link(db, user, project):
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        link, plaintext = share_link_service.create(
            db,
            project=project,
            access_type=payload.access_type,
            version_number=payload.version,
            password=payload.password,
            expires_at=payload.expires_at,
            max_views=payload.max_views,
            user_id=user.id,
        )
    except share_link_service.ShareLinkError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_service.record(
        db,
        action="share_link.create",
        target_type="share_link",
        target_id=link.id,
        workspace_id=project.workspace_id,
        user_id=user.id,
        request=request,
    )
    return ShareLinkCreateResponse(
        share_url=share_url(plaintext),
        access_type=link.access_type,
        expires_at=link.expires_at,
        link=_to_out(link),
    )


@router.delete("/share-links/{link_id}", status_code=200)
def revoke_share_link(
    link_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    link = share_link_service.get(db, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="share_link_not_found")
    proj = db.get(Project, link.project_id)
    if proj is None or not perms.can_manage_project(db, user, proj):
        raise HTTPException(status_code=403, detail="forbidden")
    share_link_service.revoke(db, link)
    audit_service.record(
        db,
        action="share_link.revoke",
        target_type="share_link",
        target_id=link.id,
        workspace_id=proj.workspace_id,
        user_id=user.id,
        request=request,
    )
    return {"status": "revoked"}

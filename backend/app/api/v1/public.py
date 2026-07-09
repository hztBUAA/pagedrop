import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_optional_user
from app.core.ratelimit import rate_limit
from app.models.page_version import PageVersion
from app.models.project import VISIBILITY_PUBLIC, Project
from app.models.user import User
from app.permissions import service as perms
from app.schemas.public import PublicPage
from app.schemas.share_link import SharePasswordVerify
from app.services import asset_service, project_service, share_link_service

router = APIRouter(prefix="/public", tags=["public"])


def _to_page(
    project: Project, workspace_slug: str, ver: PageVersion, is_latest: bool
) -> PublicPage:
    return PublicPage(
        workspace_slug=workspace_slug,
        project_slug=project.slug,
        project_id=project.id,
        title=ver.title,
        visibility=project.visibility,
        content_type=ver.content_type,
        source_content=ver.source_content,
        rendered_html=ver.rendered_html,
        version_number=ver.version_number,
        summary=ver.summary,
        is_latest=is_latest,
        noindex=project.visibility != VISIBILITY_PUBLIC,
        updated_at=ver.created_at,
    )


def _guard(db: Session, user: User | None, project: Project) -> None:
    if project.deleted_at is not None or not perms.can_view_project(db, user, project):
        raise HTTPException(status_code=404, detail="not_found")


@router.get("/projects/{workspace_slug}/{slug}/latest", response_model=PublicPage)
def public_latest(
    workspace_slug: str,
    slug: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    project = project_service.get_project_by_slugs(db, workspace_slug, slug)
    if project is None:
        raise HTTPException(status_code=404, detail="not_found")
    _guard(db, user, project)
    ver = project_service.get_latest_version(db, project)
    if ver is None:
        raise HTTPException(status_code=404, detail="no_versions")
    return _to_page(project, workspace_slug, ver, is_latest=True)


@router.get("/projects/{workspace_slug}/{slug}/versions/{version}", response_model=PublicPage)
def public_version(
    workspace_slug: str,
    slug: str,
    version: int,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    project = project_service.get_project_by_slugs(db, workspace_slug, slug)
    if project is None:
        raise HTTPException(status_code=404, detail="not_found")
    _guard(db, user, project)
    ver = project_service.get_version_by_number(db, project.id, version)
    if ver is None:
        raise HTTPException(status_code=404, detail="version_not_found")
    is_latest = project.latest_version_id == ver.id
    return _to_page(project, workspace_slug, ver, is_latest=is_latest)


def _share_page(db: Session, link, project: Project) -> PublicPage:
    if project is None or project.deleted_at is not None:
        raise HTTPException(status_code=404, detail="invalid_or_expired")
    ver = share_link_service.resolve_version(db, link, project)
    if ver is None:
        raise HTTPException(status_code=404, detail="no_versions")
    share_link_service.register_view(db, link)
    workspace_slug = project.workspace.slug
    is_latest = project.latest_version_id == ver.id
    return _to_page(project, workspace_slug, ver, is_latest=is_latest)


@router.get("/share/{share_token}", response_model=PublicPage)
def public_share(share_token: str, db: Session = Depends(get_db)):
    link = share_link_service.find_active(db, share_token)
    if link is None:
        raise HTTPException(status_code=404, detail="invalid_or_expired")
    if link.password_hash is not None:
        raise HTTPException(status_code=401, detail="password_required")
    project = db.get(Project, link.project_id)
    return _share_page(db, link, project)


@router.post(
    "/share/{share_token}/verify-password",
    response_model=PublicPage,
    dependencies=[rate_limit("share_password", limit=10, window_seconds=60)],
)
def verify_share_password(
    share_token: str,
    payload: SharePasswordVerify,
    db: Session = Depends(get_db),
):
    link = share_link_service.find_active(db, share_token)
    if link is None:
        raise HTTPException(status_code=404, detail="invalid_or_expired")
    if not share_link_service.check_password(link, payload.password):
        raise HTTPException(status_code=403, detail="invalid_password")
    project = db.get(Project, link.project_id)
    return _share_page(db, link, project)


@router.get("/assets/{asset_id}")
def public_asset(
    asset_id: uuid.UUID,
    share_token: str | None = Query(None),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    asset = asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="not_found")
    # Only assets belonging to a viewable project are served without a token.
    if asset.project_id is None:
        raise HTTPException(status_code=404, detail="not_found")
    project = db.get(Project, asset.project_id)
    if project is None or project.deleted_at is not None:
        raise HTTPException(status_code=404, detail="not_found")
    # A valid share link for this project authorizes its images too, so a
    # privately-shared page renders inline instead of showing broken images.
    allowed = perms.can_view_project(db, user, project)
    if not allowed and share_token:
        link = share_link_service.find_active(db, share_token)
        allowed = link is not None and link.project_id == project.id
    if not allowed:
        raise HTTPException(status_code=404, detail="not_found")
    return Response(
        content=asset_service.read_bytes(asset),
        media_type=asset.content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )

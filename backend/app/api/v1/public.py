from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_optional_user
from app.models.page_version import PageVersion
from app.models.project import Project, VISIBILITY_PUBLIC
from app.models.user import User
from app.permissions import service as perms
from app.schemas.public import PublicPage
from app.services import project_service

router = APIRouter(prefix="/public", tags=["public"])


def _to_page(project: Project, workspace_slug: str, ver: PageVersion, is_latest: bool) -> PublicPage:
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
    if not perms.can_view_project(db, user, project):
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

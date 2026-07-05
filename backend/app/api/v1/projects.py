import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.actor import Actor, get_actor
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.core.urls import latest_url, version_url
from app.models.page_version import SOURCE_WEB, SOURCES
from app.models.user import User
from app.models.workspace import ROLE_EDITOR
from app.permissions import service as perms
from app.schemas.project import (
    ProjectOut,
    ProjectSettingsUpdate,
    PublishRequest,
    PublishResponse,
    VersionOut,
    VersionSummary,
)
from app.services import audit_service, project_service, workspace_service

router = APIRouter(tags=["projects"])


def _authorize_publish(db: Session, actor: Actor, workspace, slug: str, source: str) -> str:
    """Return the effective source string or raise 403."""
    if actor.token is not None:
        actor.require_scope("versions:write")
        if actor.token.workspace_id != workspace.id:
            raise HTTPException(status_code=403, detail="token_workspace_mismatch")
        if not actor.token_allows_project(slug):
            raise HTTPException(status_code=403, detail="project_not_in_allowlist")
        return source if source in SOURCES and source != SOURCE_WEB else "agent"
    # Session user: must be editor+ in the workspace.
    if not perms.role_at_least(perms.get_role(db, actor.user.id, workspace.id), ROLE_EDITOR) and (
        actor.user is None or not actor.user.is_platform_admin
    ):
        raise HTTPException(status_code=403, detail="forbidden")
    return SOURCE_WEB


@router.post(
    "/projects.publish",
    response_model=PublishResponse,
    dependencies=[rate_limit("publish", limit=30, window_seconds=60)],
)
def publish(
    payload: PublishRequest,
    request: Request,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    err = payload.validate_enums()
    if err:
        raise HTTPException(status_code=422, detail=err)

    workspace = workspace_service.get_workspace_by_slug(db, payload.workspace_slug)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace_not_found")

    effective_source = _authorize_publish(db, actor, workspace, payload.slug, payload.source)

    try:
        project, ver = project_service.publish(
            db,
            workspace=workspace,
            content_type=payload.content_type,
            slug=payload.slug,
            title=payload.title,
            content=payload.content,
            visibility=payload.visibility,
            summary=payload.summary,
            changelog=payload.message,
            source=effective_source,
            user_id=actor.user_id,
            token_id=actor.token_id,
            force=payload.force,
        )
    except project_service.SecretDetectedError as exc:
        audit_service.record(
            db,
            action="secret_scan.block",
            target_type="project",
            workspace_id=workspace.id,
            user_id=actor.user_id,
            token_id=actor.token_id,
            request=request,
            metadata={"slug": payload.slug, "findings": len(exc.findings)},
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "secret_detected",
                "message": "Potential secrets were detected. Publishing was blocked.",
                "findings": [f.as_dict() for f in exc.findings],
            },
        ) from exc

    audit_service.record(
        db,
        action="version.create",
        target_type="page_version",
        target_id=ver.id,
        workspace_id=workspace.id,
        user_id=actor.user_id,
        token_id=actor.token_id,
        request=request,
        metadata={
            "slug": project.slug,
            "version": ver.version_number,
            "source": effective_source,
            "secret_scan_status": ver.secret_scan_status,
        },
    )
    return PublishResponse(
        project_id=project.id,
        version_id=ver.id,
        slug=project.slug,
        version=ver.version_number,
        latest_url=latest_url(workspace.slug, project.slug),
        version_url=version_url(workspace.slug, project.slug, ver.version_number),
        visibility=project.visibility,
        secret_scan_status=ver.secret_scan_status,
    )


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    workspace_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not perms.can_view_workspace(db, user, workspace_id):
        raise HTTPException(status_code=403, detail="forbidden")
    return project_service.list_projects(db, workspace_id)


def _load_project_for_read(
    db: Session, actor: Actor, workspace_slug: str, slug: str, scope: str
):
    """Load a project for read access by either a session user or an API token."""
    project = project_service.get_project_by_slugs(db, workspace_slug, slug)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    if actor.token is not None:
        actor.require_scope(scope)
        if actor.token.workspace_id != project.workspace_id:
            raise HTTPException(status_code=403, detail="token_workspace_mismatch")
        if not actor.token_allows_project(slug):
            raise HTTPException(status_code=403, detail="project_not_in_allowlist")
    elif not perms.can_view_project(db, actor.user, project):
        raise HTTPException(status_code=403, detail="forbidden")
    return project


def _load_project_for_manage(db: Session, user: User, workspace_slug: str, slug: str):
    project = project_service.get_project_by_slugs(db, workspace_slug, slug)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    if not perms.can_manage_project(db, user, project):
        raise HTTPException(status_code=403, detail="forbidden")
    return project


@router.get("/projects/{workspace_slug}/{slug}", response_model=ProjectOut)
def get_project(
    workspace_slug: str,
    slug: str,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return _load_project_for_read(db, actor, workspace_slug, slug, "projects:read")


@router.get("/projects/{workspace_slug}/{slug}/versions", response_model=list[VersionSummary])
def list_versions(
    workspace_slug: str,
    slug: str,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    project = _load_project_for_read(db, actor, workspace_slug, slug, "versions:read")
    return project_service.list_versions(db, project.id)


@router.get(
    "/projects/{workspace_slug}/{slug}/versions/{version}", response_model=VersionOut
)
def get_version(
    workspace_slug: str,
    slug: str,
    version: int,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    project = _load_project_for_read(db, actor, workspace_slug, slug, "versions:read")
    ver = project_service.get_version_by_number(db, project.id, version)
    if ver is None:
        raise HTTPException(status_code=404, detail="version_not_found")
    return ver


@router.patch("/projects/{workspace_slug}/{slug}/settings", response_model=ProjectOut)
def update_settings(
    workspace_slug: str,
    slug: str,
    payload: ProjectSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.project import VISIBILITIES

    project = _load_project_for_manage(db, user, workspace_slug, slug)
    if payload.visibility is not None and payload.visibility not in VISIBILITIES:
        raise HTTPException(status_code=422, detail="invalid_visibility")
    return project_service.update_settings(
        db,
        project,
        title=payload.title,
        description=payload.description,
        visibility=payload.visibility,
    )

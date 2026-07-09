import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.actor import Actor, get_actor
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.models.comment import STATUS_OPEN, STATUS_RESOLVED, STATUSES, Comment
from app.models.project import Project
from app.models.user import User
from app.permissions import service as perms
from app.schemas.comment import CommentCreate, CommentOut
from app.services import (
    audit_service,
    comment_service,
    project_service,
    share_link_service,
)

router = APIRouter(tags=["comments"])


def _viewer_may_comment(
    db: Session, actor: Actor, project: Project, share_token: str | None
) -> bool:
    """A logged-in non-member may comment on a page they can openly reach:
    public/unlisted, or private reached via a valid (non-revoked/expired) share link."""
    if perms.can_view_project(db, actor.user, project):
        return True  # public / unlisted (actor.user is set — anonymous is 401 upstream)
    if share_token:
        link = share_link_service.find_active(db, share_token)
        if link is not None and link.project_id == project.id:
            return True
    return False


def _load_project(
    db: Session,
    actor: Actor,
    workspace_slug: str,
    slug: str,
    scope: str,
    *,
    share_token: str | None = None,
    allow_public: bool = False,
) -> Project:
    """Load a project the actor may read/write comments on.

    With ``allow_public``, a logged-in non-member may read/post on a page they
    can openly reach (public/unlisted or via share token). Moderation endpoints
    leave it off, so resolve/reopen stay members-only.
    """
    project = project_service.get_project_by_slugs(db, workspace_slug, slug)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    if actor.token is not None:
        actor.require_scope(scope)
        if actor.token.workspace_id != project.workspace_id:
            raise HTTPException(status_code=403, detail="token_workspace_mismatch")
        if not actor.token_allows_project(slug):
            raise HTTPException(status_code=403, detail="project_not_in_allowlist")
        return project
    # Session user (get_actor rejects anonymous with 401 before we get here).
    if actor.user is not None and actor.user.is_platform_admin:
        return project
    is_member = (
        actor.user_id is not None
        and perms.get_role(db, actor.user_id, project.workspace_id) is not None
    )
    if is_member:
        return project
    if allow_public and _viewer_may_comment(db, actor, project, share_token):
        return project
    raise HTTPException(status_code=403, detail="forbidden")


def _author_display(actor: Actor) -> str | None:
    if actor.token is not None:
        return f"agent:{actor.token.name}"
    if actor.user is not None:
        return actor.user.name or actor.user.email
    return None


def _project_for_comment(db: Session, actor: Actor, comment: Comment, scope: str) -> Project:
    project = db.get(Project, comment.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return _load_project(db, actor, project.workspace.slug, project.slug, scope)


@router.get(
    "/projects/{workspace_slug}/{slug}/comments", response_model=list[CommentOut]
)
def list_comments(
    workspace_slug: str,
    slug: str,
    status: str | None = Query(None),
    share_token: str | None = Query(None),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    if status is not None and status not in STATUSES:
        raise HTTPException(status_code=422, detail="invalid_status")
    project = _load_project(
        db, actor, workspace_slug, slug, "comments:read",
        share_token=share_token, allow_public=True,
    )
    return comment_service.list_comments(db, project.id, status=status)


@router.post(
    "/projects/{workspace_slug}/{slug}/comments",
    response_model=CommentOut,
    dependencies=[rate_limit("comment_create", limit=60, window_seconds=60)],
)
def create_comment(
    workspace_slug: str,
    slug: str,
    payload: CommentCreate,
    request: Request,
    share_token: str | None = Query(None),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    project = _load_project(
        db, actor, workspace_slug, slug, "comments:write",
        share_token=share_token, allow_public=True,
    )

    if payload.thread_root_id is not None:
        root = comment_service.get_comment(db, payload.thread_root_id)
        if root is None or root.project_id != project.id or root.thread_root_id is not None:
            raise HTTPException(status_code=422, detail="invalid_thread_root")

    comment = comment_service.create_comment(
        db,
        project_id=project.id,
        body=payload.body,
        thread_root_id=payload.thread_root_id,
        anchor_version_number=payload.anchor_version_number,
        anchor_quote=payload.anchor_quote,
        anchor_prefix=payload.anchor_prefix,
        anchor_suffix=payload.anchor_suffix,
        author_user_id=actor.user_id,
        author_token_id=actor.token_id,
        author_source=actor.source,
        author_display=_author_display(actor),
    )
    audit_service.record(
        db,
        action="comment.create",
        target_type="comment",
        target_id=comment.id,
        workspace_id=project.workspace_id,
        user_id=actor.user_id,
        token_id=actor.token_id,
        request=request,
        metadata={"slug": project.slug, "reply": payload.thread_root_id is not None},
    )
    return comment


@router.post("/comments/{comment_id}/resolve", response_model=CommentOut)
def resolve_comment(
    comment_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    comment = comment_service.get_comment(db, comment_id)
    if comment is None or comment.thread_root_id is not None:
        raise HTTPException(status_code=404, detail="comment_not_found")
    _project_for_comment(db, actor, comment, "comments:write")
    return comment_service.set_status(db, comment, status=STATUS_RESOLVED, user_id=actor.user_id)


@router.post("/comments/{comment_id}/reopen", response_model=CommentOut)
def reopen_comment(
    comment_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    comment = comment_service.get_comment(db, comment_id)
    if comment is None or comment.thread_root_id is not None:
        raise HTTPException(status_code=404, detail="comment_not_found")
    _project_for_comment(db, actor, comment, "comments:write")
    return comment_service.set_status(db, comment, status=STATUS_OPEN, user_id=actor.user_id)


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = comment_service.get_comment(db, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="comment_not_found")
    project = db.get(Project, comment.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    is_author = comment.author_user_id is not None and comment.author_user_id == user.id
    if not is_author and not perms.can_manage_project(db, user, project):
        raise HTTPException(status_code=403, detail="forbidden")
    comment_service.delete_comment(db, comment)
    return {"status": "deleted"}

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.comment import STATUS_OPEN, STATUS_RESOLVED, Comment


def get_comment(db: Session, comment_id: uuid.UUID) -> Comment | None:
    return db.get(Comment, comment_id)


def list_comments(
    db: Session, project_id: uuid.UUID, *, status: str | None = None
) -> list[Comment]:
    stmt = select(Comment).where(Comment.project_id == project_id)
    if status is not None:
        # Filter top-level comments by status; replies always ride along with
        # their thread so agents/clients see the full conversation.
        roots = select(Comment.id).where(
            Comment.project_id == project_id,
            Comment.thread_root_id.is_(None),
            Comment.status == status,
        )
        stmt = stmt.where(
            (Comment.thread_root_id.in_(roots)) | (Comment.id.in_(roots))
        )
    return list(db.scalars(stmt.order_by(Comment.created_at.asc())))


def create_comment(
    db: Session,
    *,
    project_id: uuid.UUID,
    body: str,
    thread_root_id: uuid.UUID | None,
    anchor_version_number: int | None,
    anchor_quote: str | None,
    anchor_prefix: str | None,
    anchor_suffix: str | None,
    author_user_id: uuid.UUID | None,
    author_token_id: uuid.UUID | None,
    author_source: str,
    author_display: str | None,
) -> Comment:
    comment = Comment(
        project_id=project_id,
        thread_root_id=thread_root_id,
        anchor_version_number=anchor_version_number,
        anchor_quote=anchor_quote,
        anchor_prefix=anchor_prefix,
        anchor_suffix=anchor_suffix,
        body=body,
        status=STATUS_OPEN,
        author_user_id=author_user_id,
        author_token_id=author_token_id,
        author_source=author_source,
        author_display=author_display,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def set_status(
    db: Session, comment: Comment, *, status: str, user_id: uuid.UUID | None
) -> Comment:
    comment.status = status
    if status == STATUS_RESOLVED:
        comment.resolved_at = utcnow()
        comment.resolved_by_user_id = user_id
    else:
        comment.resolved_at = None
        comment.resolved_by_user_id = None
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, comment: Comment) -> None:
    # A top-level comment takes its replies with it.
    if comment.thread_root_id is None:
        replies = db.scalars(
            select(Comment).where(Comment.thread_root_id == comment.id)
        )
        for reply in replies:
            db.delete(reply)
    db.delete(comment)
    db.commit()

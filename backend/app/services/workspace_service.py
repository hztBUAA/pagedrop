import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.slug import random_suffix, slugify
from app.models.user import User
from app.models.workspace import (
    ROLE_OWNER,
    WORKSPACE_TEAM,
    Workspace,
    WorkspaceMember,
)
from app.services.auth_service import get_user_by_email


class WorkspaceError(Exception):
    pass


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    while db.scalar(select(Workspace).where(Workspace.slug == slug)) is not None:
        slug = f"{base}-{random_suffix(4)}"
    return slug


def list_for_user(db: Session, user: User) -> list[tuple[Workspace, str]]:
    rows = db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at)
    ).all()
    return [(ws, role) for ws, role in rows]


def create_team_workspace(db: Session, user: User, name: str) -> Workspace:
    slug = _unique_slug(db, slugify(name, fallback="team"))
    ws = Workspace(name=name, slug=slug, type=WORKSPACE_TEAM, owner_user_id=user.id)
    db.add(ws)
    db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=ROLE_OWNER))
    db.commit()
    db.refresh(ws)
    return ws


def get_workspace(db: Session, workspace_id: uuid.UUID) -> Workspace | None:
    return db.get(Workspace, workspace_id)


def get_workspace_by_slug(db: Session, slug: str) -> Workspace | None:
    return db.scalar(select(Workspace).where(Workspace.slug == slug))


def list_members(db: Session, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
    return list(
        db.scalars(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
        )
    )


def add_member(db: Session, workspace_id: uuid.UUID, email: str, role: str) -> WorkspaceMember:
    user = get_user_by_email(db, email)
    if user is None:
        raise WorkspaceError("user_not_found")
    existing = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if existing is not None:
        raise WorkspaceError("already_member")
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member

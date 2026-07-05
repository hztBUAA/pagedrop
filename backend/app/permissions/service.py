"""Centralized authorization. All access decisions live here, never in handlers."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project, VISIBILITY_PRIVATE
from app.models.user import User
from app.models.workspace import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_ORDER,
    ROLE_OWNER,
    WorkspaceMember,
)


def get_role(db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID) -> str | None:
    return db.scalar(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )


def role_at_least(role: str | None, minimum: str) -> bool:
    if role is None:
        return False
    return ROLE_ORDER.get(role, -1) >= ROLE_ORDER[minimum]


# --- Project access ---
def can_view_project(db: Session, user: User | None, project: Project) -> bool:
    if project.visibility != VISIBILITY_PRIVATE:
        return True
    if user is None:
        return False
    if user.is_platform_admin:
        return True
    return get_role(db, user.id, project.workspace_id) is not None


def can_edit_project(db: Session, user: User | None, project: Project) -> bool:
    """Create versions / edit content requires editor+ membership."""
    if user is None:
        return False
    if user.is_platform_admin:
        return True
    return role_at_least(get_role(db, user.id, project.workspace_id), ROLE_EDITOR)


def can_create_version(db: Session, user: User | None, project: Project) -> bool:
    return can_edit_project(db, user, project)


def can_manage_project(db: Session, user: User | None, project: Project) -> bool:
    """Settings, visibility, delete, share links require admin+."""
    if user is None:
        return False
    if user.is_platform_admin:
        return True
    return role_at_least(get_role(db, user.id, project.workspace_id), ROLE_ADMIN)


def can_create_share_link(db: Session, user: User | None, project: Project) -> bool:
    return can_manage_project(db, user, project)


# --- Workspace access ---
def can_view_workspace(db: Session, user: User, workspace_id: uuid.UUID) -> bool:
    if user.is_platform_admin:
        return True
    return get_role(db, user.id, workspace_id) is not None


def can_manage_tokens(db: Session, user: User, workspace_id: uuid.UUID) -> bool:
    if user.is_platform_admin:
        return True
    return role_at_least(get_role(db, user.id, workspace_id), ROLE_ADMIN)


def can_manage_members(db: Session, user: User, workspace_id: uuid.UUID) -> bool:
    if user.is_platform_admin:
        return True
    return role_at_least(get_role(db, user.id, workspace_id), ROLE_ADMIN)


def is_workspace_owner(db: Session, user: User, workspace_id: uuid.UUID) -> bool:
    if user.is_platform_admin:
        return True
    return get_role(db, user.id, workspace_id) == ROLE_OWNER

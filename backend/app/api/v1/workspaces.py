import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.actor import Actor, get_actor
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.workspace import ROLE_ORDER, ROLE_OWNER
from app.permissions import service as perms
from app.schemas.workspace import (
    MemberAdd,
    MemberOut,
    WorkspaceCreate,
    WorkspaceWithRole,
)
from app.services import workspace_service as ws_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceWithRole])
def list_workspaces(actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    # A token is bound to a single workspace, so it only ever sees that one.
    if actor.token is not None:
        actor.require_scope("projects:read")
        ws = ws_service.get_workspace(db, actor.token.workspace_id)
        if ws is None:
            return []
        item = WorkspaceWithRole.model_validate(ws)
        item.role = (perms.get_role(db, actor.user_id, ws.id) or "") if actor.user_id else ""
        return [item]
    out = []
    for ws, role in ws_service.list_for_user(db, actor.user):
        item = WorkspaceWithRole.model_validate(ws)
        item.role = role
        out.append(item)
    return out


@router.post("", response_model=WorkspaceWithRole, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ws = ws_service.create_team_workspace(db, user, payload.name)
    item = WorkspaceWithRole.model_validate(ws)
    item.role = ROLE_OWNER
    return item


def _load_workspace_for_view(db: Session, user: User, workspace_id: uuid.UUID):
    ws = ws_service.get_workspace(db, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace_not_found")
    if not perms.can_view_workspace(db, user, workspace_id):
        raise HTTPException(status_code=403, detail="forbidden")
    return ws


@router.get("/{workspace_id}", response_model=WorkspaceWithRole)
def get_workspace(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ws = _load_workspace_for_view(db, user, workspace_id)
    item = WorkspaceWithRole.model_validate(ws)
    item.role = perms.get_role(db, user.id, workspace_id) or ""
    return item


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
def list_members(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _load_workspace_for_view(db, user, workspace_id)
    return ws_service.list_members(db, workspace_id)


@router.post("/{workspace_id}/members", response_model=MemberOut, status_code=201)
def add_member(
    workspace_id: uuid.UUID,
    payload: MemberAdd,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not perms.can_manage_members(db, user, workspace_id):
        raise HTTPException(status_code=403, detail="forbidden")
    if payload.role not in ROLE_ORDER:
        raise HTTPException(status_code=422, detail="invalid_role")
    try:
        return ws_service.add_member(db, workspace_id, payload.email, payload.role)
    except ws_service.WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

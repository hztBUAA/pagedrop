import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    if request.client:
        return request.client.host
    return None


def record(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    token_id: uuid.UUID | None = None,
    request: Request | None = None,
    metadata: dict | None = None,
    commit: bool = True,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        target_type=target_type,
        target_id=target_id,
        workspace_id=workspace_id,
        user_id=user_id,
        token_id=token_id,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent") if request else None,
        audit_metadata=metadata,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry

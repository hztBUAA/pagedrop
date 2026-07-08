from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.core.slug import random_suffix, slugify
from app.models.user import User
from app.models.workspace import (
    ROLE_OWNER,
    WORKSPACE_PERSONAL,
    Workspace,
    WorkspaceMember,
)


class AuthError(Exception):
    """Raised for auth failures (duplicate email, bad credentials)."""


def _unique_workspace_slug(db: Session, base: str) -> str:
    slug = base
    while db.scalar(select(Workspace).where(Workspace.slug == slug)) is not None:
        slug = f"{base}-{random_suffix(4)}"
    return slug


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def register_user(db: Session, email: str, password: str, name: str | None) -> User:
    email = email.lower()
    if get_user_by_email(db, email) is not None:
        raise AuthError("email_already_registered")

    user = User(email=email, name=name, password_hash=hash_password(password))
    db.add(user)
    db.flush()  # assign user.id

    # Auto-create a personal workspace with the user as owner.
    display = name or email.split("@")[0]
    base_slug = _unique_workspace_slug(db, slugify(display, fallback="personal"))
    workspace = Workspace(
        name=display,
        slug=base_slug,
        type=WORKSPACE_PERSONAL,
        owner_user_id=user.id,
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=ROLE_OWNER)
    )
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("invalid_credentials")
    return user


def set_password(db: Session, email: str, new_password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None:
        raise AuthError("user_not_found")
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user

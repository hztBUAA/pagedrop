from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.core.slug import random_suffix, slugify
from app.models.oauth_identity import OAuthIdentity
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


def get_user_by_oauth(db: Session, provider: str, account_id: str) -> User | None:
    identity = db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == provider,
            OAuthIdentity.provider_account_id == str(account_id),
        )
    )
    return identity.user if identity is not None else None


def _ensure_personal_workspace(db: Session, user: User, display: str) -> None:
    """Create the user's personal workspace + owner membership (assumes user.id is set)."""
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


def register_user(db: Session, email: str, password: str, name: str | None) -> User:
    email = email.lower()
    if get_user_by_email(db, email) is not None:
        raise AuthError("email_already_registered")

    user = User(email=email, name=name, password_hash=hash_password(password))
    db.add(user)
    db.flush()  # assign user.id

    display = name or email.split("@")[0]
    _ensure_personal_workspace(db, user, display)
    db.commit()
    db.refresh(user)
    return user


def upsert_oauth_user(
    db: Session,
    *,
    provider: str,
    provider_account_id: str,
    login: str,
    email: str,
    name: str | None,
) -> User:
    """Find or create the PageDrop account for a verified third-party identity.

    Resolution order: existing (provider, account) identity → existing verified
    email (link a new identity) → create a passwordless account + identity.
    """
    provider_account_id = str(provider_account_id)
    email = email.lower()

    identity = db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == provider,
            OAuthIdentity.provider_account_id == provider_account_id,
        )
    )
    if identity is not None:
        changed = False
        if login and identity.provider_login != login:
            identity.provider_login = login
            changed = True
        if email and identity.email != email:
            identity.email = email
            changed = True
        if changed:
            db.commit()
        return identity.user

    def _new_identity(user: User) -> OAuthIdentity:
        return OAuthIdentity(
            user_id=user.id,
            provider=provider,
            provider_account_id=provider_account_id,
            provider_login=login or None,
            email=email or None,
        )

    # Link to an existing account with the same (provider-verified) email.
    user = get_user_by_email(db, email)
    if user is not None:
        db.add(_new_identity(user))
        db.commit()
        db.refresh(user)
        return user

    # Brand-new OAuth-only account (no local password).
    user = User(email=email, name=name or login, password_hash=None)
    db.add(user)
    db.flush()
    _ensure_personal_workspace(db, user, name or login or email.split("@")[0])
    db.add(_new_identity(user))
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
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

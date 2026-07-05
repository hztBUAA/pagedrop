import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import generate_token, hash_password, hash_token, verify_password
from app.models.page_version import PageVersion
from app.models.project import Project
from app.models.share_link import ACCESS_FIXED_VERSION, ACCESS_LATEST, ShareLink

SHARE_PREFIX = "pds_"


class ShareLinkError(Exception):
    pass


def create(
    db: Session,
    *,
    project: Project,
    access_type: str,
    version_number: int | None,
    password: str | None,
    expires_at: datetime | None,
    max_views: int | None,
    user_id: uuid.UUID,
) -> tuple[ShareLink, str]:
    if access_type not in (ACCESS_LATEST, ACCESS_FIXED_VERSION):
        raise ShareLinkError("invalid_access_type")

    version_id = None
    if access_type == ACCESS_FIXED_VERSION:
        if version_number is None:
            raise ShareLinkError("version_required")
        ver = db.scalar(
            select(PageVersion).where(
                PageVersion.project_id == project.id,
                PageVersion.version_number == version_number,
            )
        )
        if ver is None:
            raise ShareLinkError("version_not_found")
        version_id = ver.id

    plaintext = generate_token(SHARE_PREFIX)
    link = ShareLink(
        project_id=project.id,
        version_id=version_id,
        token_hash=hash_token(plaintext),
        access_type=access_type,
        password_hash=hash_password(password) if password else None,
        expires_at=expires_at,
        max_views=max_views,
        created_by_user_id=user_id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link, plaintext


def list_for_project(db: Session, project_id: uuid.UUID) -> list[ShareLink]:
    return list(
        db.scalars(
            select(ShareLink)
            .where(ShareLink.project_id == project_id)
            .order_by(ShareLink.created_at.desc())
        )
    )


def get(db: Session, link_id: uuid.UUID) -> ShareLink | None:
    return db.get(ShareLink, link_id)


def revoke(db: Session, link: ShareLink) -> None:
    if link.revoked_at is None:
        link.revoked_at = datetime.now(timezone.utc)
        db.commit()


def find_active(db: Session, raw_token: str) -> ShareLink | None:
    link = db.scalar(select(ShareLink).where(ShareLink.token_hash == hash_token(raw_token)))
    if link is None or link.revoked_at is not None:
        return None
    if link.expires_at is not None:
        exp = link.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
    if link.max_views is not None and link.view_count >= link.max_views:
        return None
    return link


def check_password(link: ShareLink, password: str | None) -> bool:
    if link.password_hash is None:
        return True
    if password is None:
        return False
    return verify_password(password, link.password_hash)


def register_view(db: Session, link: ShareLink) -> None:
    link.view_count += 1
    db.commit()


def resolve_version(db: Session, link: ShareLink, project: Project) -> PageVersion | None:
    if link.access_type == ACCESS_FIXED_VERSION and link.version_id is not None:
        return db.get(PageVersion, link.version_id)
    if project.latest_version_id is not None:
        return db.get(PageVersion, project.latest_version_id)
    return None

import hashlib
import re
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.asset import ALLOWED_IMAGE_TYPES, Asset
from app.services import storage

_ASSET_REF = re.compile(r"pagedrop://asset/([0-9a-fA-F-]{8,})")


class AssetTooLargeError(Exception):
    pass


class UnsupportedAssetTypeError(Exception):
    pass


def _storage_key(workspace_id: uuid.UUID, sha256: str) -> str:
    return f"{workspace_id.hex}/{sha256[:2]}/{sha256}"


def get_asset(db: Session, asset_id: uuid.UUID) -> Asset | None:
    return db.get(Asset, asset_id)


def create_asset(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    data: bytes,
    content_type: str,
    original_name: str | None,
    max_bytes: int,
    user_id: uuid.UUID | None,
    token_id: uuid.UUID | None,
    source: str,
) -> Asset:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise UnsupportedAssetTypeError(content_type)
    if len(data) > max_bytes:
        raise AssetTooLargeError(len(data))

    sha256 = hashlib.sha256(data).hexdigest()

    # Content-addressed dedup within the workspace.
    existing = db.scalar(
        select(Asset).where(Asset.workspace_id == workspace_id, Asset.sha256 == sha256)
    )
    if existing is not None:
        return existing

    key = _storage_key(workspace_id, sha256)
    storage.get_backend().put(key, data)

    asset = Asset(
        workspace_id=workspace_id,
        project_id=project_id,
        sha256=sha256,
        content_type=content_type,
        byte_size=len(data),
        storage_key=key,
        original_name=original_name,
        created_by_user_id=user_id,
        created_by_token_id=token_id,
        created_by_source=source,
    )
    db.add(asset)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent upload of the same bytes won the unique constraint race;
        # fall back to the row it inserted (the blob is already on disk).
        db.rollback()
        return db.scalar(
            select(Asset).where(
                Asset.workspace_id == workspace_id, Asset.sha256 == sha256
            )
        )
    db.refresh(asset)
    return asset


def read_bytes(asset: Asset) -> bytes:
    return storage.get_backend().get(asset.storage_key)


def link_referenced_assets(
    db: Session, *, workspace_id: uuid.UUID, project_id: uuid.UUID, content: str
) -> int:
    """Attach workspace-scoped assets referenced in content to a project.

    Images uploaded before a project exists are workspace-scoped (project_id
    NULL) and cannot be served from the public asset endpoint. On publish we
    claim any such assets referenced by the content so the public page can
    render them. Assets already owned by another project are left untouched.
    """
    ids: set[uuid.UUID] = set()
    for raw in _ASSET_REF.findall(content):
        try:
            ids.add(uuid.UUID(raw))
        except ValueError:
            continue
    if not ids:
        return 0
    assets = db.scalars(
        select(Asset).where(
            Asset.id.in_(ids),
            Asset.workspace_id == workspace_id,
            Asset.project_id.is_(None),
        )
    ).all()
    for asset in assets:
        asset.project_id = project_id
    return len(assets)

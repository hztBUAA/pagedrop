import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.page_version import (
    SCAN_OVERRIDDEN,
    SCAN_PASSED,
    PageVersion,
)
from app.models.project import Project
from app.models.workspace import Workspace
from app.render import service as render_service
from app.services import asset_service, secret_scan_service


class SecretDetectedError(Exception):
    def __init__(self, findings):
        self.findings = findings
        super().__init__("secret_detected")


def get_project(db: Session, workspace_id: uuid.UUID, slug: str) -> Project | None:
    return db.scalar(
        select(Project).where(Project.workspace_id == workspace_id, Project.slug == slug)
    )


def get_project_by_slugs(db: Session, workspace_slug: str, slug: str) -> Project | None:
    return db.scalar(
        select(Project)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .where(Workspace.slug == workspace_slug, Project.slug == slug)
    )


def list_projects(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    q: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Project]:
    stmt = select(Project).where(Project.workspace_id == workspace_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Project.title.ilike(like) | Project.slug.ilike(like))
    stmt = stmt.order_by(Project.updated_at.desc()).offset(max(offset, 0))
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def _next_version_number(db: Session, project_id: uuid.UUID) -> int:
    current = db.scalar(
        select(func.max(PageVersion.version_number)).where(
            PageVersion.version_number.isnot(None),
            PageVersion.project_id == project_id,
        )
    )
    return (current or 0) + 1


def list_versions(db: Session, project_id: uuid.UUID) -> list[PageVersion]:
    return list(
        db.scalars(
            select(PageVersion)
            .where(PageVersion.project_id == project_id)
            .order_by(PageVersion.version_number.desc())
        )
    )


def get_version_by_number(db: Session, project_id: uuid.UUID, number: int) -> PageVersion | None:
    return db.scalar(
        select(PageVersion).where(
            PageVersion.project_id == project_id, PageVersion.version_number == number
        )
    )


def get_latest_version(db: Session, project: Project) -> PageVersion | None:
    if project.latest_version_id is None:
        return None
    return db.get(PageVersion, project.latest_version_id)


def publish(
    db: Session,
    *,
    workspace: Workspace,
    content_type: str,
    slug: str,
    title: str,
    content: str,
    visibility: str,
    summary: str | None,
    changelog: str | None,
    source: str,
    user_id: uuid.UUID | None,
    token_id: uuid.UUID | None,
    force: bool = False,
) -> tuple[Project, PageVersion]:
    findings = secret_scan_service.scan(content)
    if findings and not force:
        raise SecretDetectedError(findings)
    scan_status = SCAN_OVERRIDDEN if findings else SCAN_PASSED

    project = get_project(db, workspace.id, slug)
    is_new = project is None
    if is_new:
        project = Project(
            workspace_id=workspace.id,
            slug=slug,
            title=title,
            default_content_type=content_type,
            visibility=visibility,
            created_by_user_id=user_id or workspace.owner_user_id,
        )
        db.add(project)
        db.flush()

    version_number = _next_version_number(db, project.id)
    rendered = render_service.prepare_content(content_type, content)
    if summary is None:
        summary = render_service.make_summary(content_type, content)

    version = PageVersion(
        project_id=project.id,
        version_number=version_number,
        content_type=content_type,
        source_content=content,
        rendered_html=rendered,
        title=title,
        summary=summary,
        changelog=changelog,
        created_by_user_id=user_id,
        created_by_token_id=token_id,
        created_by_source=source,
        secret_scan_status=scan_status,
    )
    db.add(version)
    db.flush()

    # Never overwrite old versions; only advance the latest pointer + title.
    project.latest_version_id = version.id
    project.title = title
    asset_service.link_referenced_assets(
        db, workspace_id=workspace.id, project_id=project.id, content=content
    )
    db.commit()
    db.refresh(project)
    db.refresh(version)
    return project, version


def update_settings(
    db: Session,
    project: Project,
    *,
    title: str | None,
    description: str | None,
    visibility: str | None,
) -> Project:
    if title is not None:
        project.title = title
    if description is not None:
        project.description = description
    if visibility is not None:
        project.visibility = visibility
    db.commit()
    db.refresh(project)
    return project

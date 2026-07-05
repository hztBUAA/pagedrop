from app.core.config import settings


def _base() -> str:
    return settings.app_base_url.rstrip("/")


def latest_url(workspace_slug: str, project_slug: str) -> str:
    return f"{_base()}/p/{workspace_slug}/{project_slug}"


def version_url(workspace_slug: str, project_slug: str, version: int) -> str:
    return f"{_base()}/p/{workspace_slug}/{project_slug}/v/{version}"


def share_url(share_token: str) -> str:
    return f"{_base()}/share/{share_token}"

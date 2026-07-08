import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _register(client, email):
    from tests.conftest import issue_register_code

    code = issue_register_code(email)
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "S", "code": code},
    )


@pytest.fixture
def owner():
    with TestClient(app) as c:
        _register(c, f"share-{uuid.uuid4().hex[:8]}@example.com")
        c.workspace_slug = c.get("/api/v1/workspaces").json()[0]["slug"]
        yield c


def _publish(client, slug, visibility="private", content="# secret doc"):
    return client.post(
        "/api/v1/projects.publish",
        json={
            "workspace_slug": client.workspace_slug,
            "slug": slug,
            "title": "Doc",
            "content_type": "markdown",
            "content": content,
            "visibility": visibility,
        },
    )


def _create_link(client, slug, **kw):
    return client.post(
        f"/api/v1/projects/{client.workspace_slug}/{slug}/share-links",
        json=kw,
    )


def _token_from_url(url: str) -> str:
    return url.rstrip("/").split("/share/")[-1]


def test_share_link_grants_access_to_private(owner):
    _publish(owner, "s1")
    resp = _create_link(owner, "s1", access_type="latest")
    assert resp.status_code == 201
    token = _token_from_url(resp.json()["share_url"])

    with TestClient(app) as anon:
        page = anon.get(f"/api/v1/public/share/{token}")
        assert page.status_code == 200
        assert page.json()["source_content"] == "# secret doc"


def test_password_protected_share(owner):
    _publish(owner, "s2")
    token = _token_from_url(
        _create_link(owner, "s2", access_type="latest", password="hunter2").json()["share_url"]
    )
    with TestClient(app) as anon:
        # bare GET is blocked
        assert anon.get(f"/api/v1/public/share/{token}").status_code == 401
        # wrong password
        bad = anon.post(
            f"/api/v1/public/share/{token}/verify-password", json={"password": "nope"}
        )
        assert bad.status_code == 403
        # correct password
        ok = anon.post(
            f"/api/v1/public/share/{token}/verify-password", json={"password": "hunter2"}
        )
        assert ok.status_code == 200


def test_expired_share_link(owner):
    _publish(owner, "s3")
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    token = _token_from_url(
        _create_link(owner, "s3", access_type="latest", expires_at=past).json()["share_url"]
    )
    with TestClient(app) as anon:
        assert anon.get(f"/api/v1/public/share/{token}").status_code == 404


def test_revoked_share_link(owner):
    _publish(owner, "s4")
    created = _create_link(owner, "s4", access_type="latest").json()
    token = _token_from_url(created["share_url"])
    link_id = created["link"]["id"]
    owner.delete(f"/api/v1/share-links/{link_id}")
    with TestClient(app) as anon:
        assert anon.get(f"/api/v1/public/share/{token}").status_code == 404


def test_fixed_version_share(owner):
    _publish(owner, "s5", content="v1")
    _publish(owner, "s5", content="v2")
    token = _token_from_url(
        _create_link(owner, "s5", access_type="fixed_version", version=1).json()["share_url"]
    )
    with TestClient(app) as anon:
        page = anon.get(f"/api/v1/public/share/{token}").json()
        assert page["source_content"] == "v1"
        assert page["version_number"] == 1


def test_max_views_enforced(owner):
    _publish(owner, "s6")
    token = _token_from_url(
        _create_link(owner, "s6", access_type="latest", max_views=1).json()["share_url"]
    )
    with TestClient(app) as anon:
        assert anon.get(f"/api/v1/public/share/{token}").status_code == 200
        assert anon.get(f"/api/v1/public/share/{token}").status_code == 404

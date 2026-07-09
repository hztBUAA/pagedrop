import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

# 1x1 transparent PNG
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _register(client, email, name="User"):
    from tests.conftest import issue_register_code

    code = issue_register_code(email)
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": name, "code": code},
    )


@pytest.fixture
def owner_client():
    with TestClient(app) as c:
        _register(c, f"asset-{uuid.uuid4().hex[:8]}@example.com", name="Owner")
        ws = c.get("/api/v1/workspaces").json()[0]
        c.workspace_slug = ws["slug"]
        yield c


def _publish(client, slug="doc", content="# Hi", visibility="private"):
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


def _upload(client, project_slug=None, content_type="image/png", data=PNG_BYTES):
    form = {"workspace_slug": client.workspace_slug}
    if project_slug:
        form["project_slug"] = project_slug
    return client.post(
        "/api/v1/assets",
        files={"file": ("pic.png", data, content_type)},
        data=form,
    )


def test_upload_returns_ref(owner_client):
    _publish(owner_client, slug="withimg")
    resp = _upload(owner_client, project_slug="withimg")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ref"] == f"pagedrop://asset/{body['id']}"
    assert body["content_type"] == "image/png"


def test_upload_dedups_by_hash(owner_client):
    _publish(owner_client, slug="dd")
    a = _upload(owner_client, project_slug="dd").json()
    b = _upload(owner_client, project_slug="dd").json()
    assert a["id"] == b["id"]


def test_unsupported_type_rejected(owner_client):
    resp = _upload(owner_client, content_type="application/pdf", data=b"%PDF-1.4")
    assert resp.status_code == 415


def test_get_asset_bytes_roundtrip(owner_client):
    _publish(owner_client, slug="rt")
    asset_id = _upload(owner_client, project_slug="rt").json()["id"]
    resp = owner_client.get(f"/api/v1/assets/{asset_id}")
    assert resp.status_code == 200
    assert resp.content == PNG_BYTES
    assert resp.headers["content-type"] == "image/png"


def test_private_asset_hidden_from_anon(owner_client):
    _publish(owner_client, slug="priv", visibility="private")
    asset_id = _upload(owner_client, project_slug="priv").json()["id"]
    with TestClient(app) as anon:
        resp = anon.get(f"/api/v1/public/assets/{asset_id}")
        assert resp.status_code == 404


def test_private_asset_served_via_share_token(owner_client):
    _publish(owner_client, slug="shr", visibility="private")
    asset_id = _upload(owner_client, project_slug="shr").json()["id"]
    created = owner_client.post(
        f"/api/v1/projects/{owner_client.workspace_slug}/shr/share-links",
        json={"access_type": "latest"},
    )
    token = created.json()["share_url"].rsplit("/share/", 1)[1]
    with TestClient(app) as anon:
        # Without the token the private image is hidden.
        assert anon.get(f"/api/v1/public/assets/{asset_id}").status_code == 404
        # With a valid share token for the same project, it resolves.
        ok = anon.get(f"/api/v1/public/assets/{asset_id}?share_token={token}")
        assert ok.status_code == 200, ok.text
        assert ok.content == PNG_BYTES
        # A bogus token stays blocked.
        assert (
            anon.get(f"/api/v1/public/assets/{asset_id}?share_token=nope").status_code
            == 404
        )


def test_public_asset_served_to_anon(owner_client):
    _publish(owner_client, slug="pubdoc", visibility="public")
    asset_id = _upload(owner_client, project_slug="pubdoc").json()["id"]
    with TestClient(app) as anon:
        resp = anon.get(f"/api/v1/public/assets/{asset_id}")
        assert resp.status_code == 200
        assert resp.content == PNG_BYTES


def test_upload_requires_membership(owner_client):
    _publish(owner_client, slug="mine")
    asset_id = _upload(owner_client, project_slug="mine").json()["id"]
    with TestClient(app) as other:
        _register(other, f"intruder-{uuid.uuid4().hex[:6]}@example.com")
        # Cannot read another workspace's private asset.
        resp = other.get(f"/api/v1/assets/{asset_id}")
        assert resp.status_code == 404


def test_token_allowlist_enforced_on_asset_read(owner_client):
    # Asset attached to project "secret"; a token allowlisted to a different
    # project must not be able to read it (IDOR guard).
    _publish(owner_client, slug="secret")
    asset_id = _upload(owner_client, project_slug="secret").json()["id"]
    token = owner_client.post(
        "/api/v1/tokens",
        json={
            "workspace_slug": owner_client.workspace_slug,
            "name": "scoped",
            "scopes": ["versions:read"],
            "project_allowlist": ["other-project"],
        },
    ).json()["token"]
    with TestClient(app) as api:
        headers = {"Authorization": f"Bearer {token}"}
        denied = api.get(f"/api/v1/assets/{asset_id}", headers=headers)
        assert denied.status_code == 404
    # A token without an allowlist (full workspace) can read it.
    open_token = owner_client.post(
        "/api/v1/tokens",
        json={
            "workspace_slug": owner_client.workspace_slug,
            "name": "open",
            "scopes": ["versions:read"],
            "project_allowlist": None,
        },
    ).json()["token"]
    with TestClient(app) as api:
        ok = api.get(
            f"/api/v1/assets/{asset_id}",
            headers={"Authorization": f"Bearer {open_token}"},
        )
        assert ok.status_code == 200


def test_publish_links_workspace_scoped_asset(owner_client):
    # Simulate the new-page flow: upload before the project exists (no
    # project_slug), then publish content referencing the asset.
    asset_id = _upload(owner_client).json()["id"]
    with TestClient(app) as anon:
        # Not yet viewable publicly (workspace-scoped, project_id is NULL).
        assert anon.get(f"/api/v1/public/assets/{asset_id}").status_code == 404
    _publish(
        owner_client,
        slug="linked",
        content=f"# Hi\n\n![pic](pagedrop://asset/{asset_id})",
        visibility="public",
    )
    with TestClient(app) as anon:
        resp = anon.get(f"/api/v1/public/assets/{asset_id}")
        assert resp.status_code == 200
        assert resp.content == PNG_BYTES


import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _register(client, email):
    from tests.conftest import issue_register_code

    code = issue_register_code(email)
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "T", "code": code},
    )


@pytest.fixture
def owner():
    with TestClient(app) as c:
        _register(c, f"tok-{uuid.uuid4().hex[:8]}@example.com")
        c.workspace_slug = c.get("/api/v1/workspaces").json()[0]["slug"]
        c.workspace_id = c.get("/api/v1/workspaces").json()[0]["id"]
        yield c


def _create_token(client, scopes, allowlist=None):
    return client.post(
        "/api/v1/tokens",
        json={
            "workspace_slug": client.workspace_slug,
            "name": "agent",
            "scopes": scopes,
            "project_allowlist": allowlist,
        },
    )


def test_token_shown_once_and_prefixed(owner):
    resp = _create_token(owner, ["projects:write", "versions:write"])
    assert resp.status_code == 201
    body = resp.json()
    assert body["token"].startswith("pd_live_")
    assert body["token_info"]["token_prefix"].startswith("pd_live_")
    # listing never returns plaintext
    listed = owner.get(f"/api/v1/tokens?workspace_id={owner.workspace_id}").json()
    assert "token" not in listed[0]
    assert listed[0]["token_prefix"].startswith("pd_live_")


def test_invalid_scope_rejected(owner):
    resp = _create_token(owner, ["projects:destroy"])
    assert resp.status_code == 422


def _publish_with_token(token, workspace_slug, slug="agent-doc", content="# hi"):
    with TestClient(app) as api:
        return api.post(
            "/api/v1/projects.publish",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "workspace_slug": workspace_slug,
                "slug": slug,
                "title": "Agent Doc",
                "content_type": "markdown",
                "content": content,
                "visibility": "private",
                "source": "agent",
            },
        )


def test_api_publish_with_token(owner):
    token = _create_token(owner, ["projects:write", "versions:write"]).json()["token"]
    resp = _publish_with_token(token, owner.workspace_slug)
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] == 1


def test_token_scope_insufficient(owner):
    token = _create_token(owner, ["projects:read"]).json()["token"]
    resp = _publish_with_token(token, owner.workspace_slug)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "insufficient_scope"


def test_token_allowlist_enforced(owner):
    token = _create_token(
        owner, ["versions:write"], allowlist=["allowed-slug"]
    ).json()["token"]
    denied = _publish_with_token(token, owner.workspace_slug, slug="other-slug")
    assert denied.status_code == 403
    allowed = _publish_with_token(token, owner.workspace_slug, slug="allowed-slug")
    assert allowed.status_code == 200


def test_revoked_token_fails(owner):
    created = _create_token(owner, ["versions:write"]).json()
    token = created["token"]
    token_id = created["token_info"]["id"]
    assert _publish_with_token(token, owner.workspace_slug, slug="a").status_code == 200
    owner.delete(f"/api/v1/tokens/{token_id}")
    resp = _publish_with_token(token, owner.workspace_slug, slug="b")
    assert resp.status_code == 401


def test_last_used_updates(owner):
    token = _create_token(owner, ["versions:write"]).json()["token"]
    _publish_with_token(token, owner.workspace_slug, slug="lu")
    listed = owner.get(f"/api/v1/tokens?workspace_id={owner.workspace_id}").json()
    assert listed[0]["last_used_at"] is not None


def test_token_read_versions(owner):
    token = _create_token(owner, ["versions:write", "versions:read"]).json()["token"]
    _publish_with_token(token, owner.workspace_slug, slug="readable")
    with TestClient(app) as api:
        headers = {"Authorization": f"Bearer {token}"}
        vers = api.get(
            f"/api/v1/projects/{owner.workspace_slug}/readable/versions",
            headers=headers,
        )
        assert vers.status_code == 200, vers.text
        assert len(vers.json()) == 1


def test_token_read_requires_scope(owner):
    # write-only token cannot list versions
    token = _create_token(owner, ["versions:write"]).json()["token"]
    _publish_with_token(token, owner.workspace_slug, slug="noread")
    with TestClient(app) as api:
        resp = api.get(
            f"/api/v1/projects/{owner.workspace_slug}/noread/versions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "insufficient_scope"

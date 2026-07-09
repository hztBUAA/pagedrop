import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


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
        _register(c, f"cmt-{uuid.uuid4().hex[:8]}@example.com", name="Owner")
        ws = c.get("/api/v1/workspaces").json()[0]
        c.workspace_slug = ws["slug"]
        yield c


def _publish(client, slug="doc", visibility="private"):
    return client.post(
        "/api/v1/projects.publish",
        json={
            "workspace_slug": client.workspace_slug,
            "slug": slug,
            "title": "Doc",
            "content_type": "markdown",
            "content": "The quick brown fox jumps.",
            "visibility": visibility,
        },
    )


def _base(client, slug="doc"):
    return f"/api/v1/projects/{client.workspace_slug}/{slug}"


def test_create_and_list_comment(owner_client):
    _publish(owner_client)
    resp = owner_client.post(
        _base(owner_client) + "/comments",
        json={"body": "fix this", "anchor_quote": "quick brown", "anchor_version_number": 1},
    )
    assert resp.status_code == 200, resp.text
    c = resp.json()
    assert c["status"] == "open"
    assert c["author_display"]

    listed = owner_client.get(_base(owner_client) + "/comments").json()
    assert len(listed) == 1
    assert listed[0]["anchor_quote"] == "quick brown"


def test_reply_threads_to_root(owner_client):
    _publish(owner_client)
    root = owner_client.post(
        _base(owner_client) + "/comments", json={"body": "top"}
    ).json()
    reply = owner_client.post(
        _base(owner_client) + "/comments",
        json={"body": "reply", "thread_root_id": root["id"]},
    )
    assert reply.status_code == 200
    assert reply.json()["thread_root_id"] == root["id"]


def test_resolve_and_status_filter(owner_client):
    _publish(owner_client)
    c = owner_client.post(_base(owner_client) + "/comments", json={"body": "todo"}).json()
    owner_client.post(f"/api/v1/comments/{c['id']}/resolve")

    open_only = owner_client.get(_base(owner_client) + "/comments?status=open").json()
    assert open_only == []
    resolved = owner_client.get(_base(owner_client) + "/comments?status=resolved").json()
    assert len(resolved) == 1
    assert resolved[0]["status"] == "resolved"

    owner_client.post(f"/api/v1/comments/{c['id']}/reopen")
    assert len(owner_client.get(_base(owner_client) + "/comments?status=open").json()) == 1


def test_status_filter_includes_replies(owner_client):
    _publish(owner_client)
    root = owner_client.post(_base(owner_client) + "/comments", json={"body": "root"}).json()
    owner_client.post(
        _base(owner_client) + "/comments",
        json={"body": "reply", "thread_root_id": root["id"]},
    )
    open_thread = owner_client.get(_base(owner_client) + "/comments?status=open").json()
    assert len(open_thread) == 2


def test_delete_comment(owner_client):
    _publish(owner_client)
    c = owner_client.post(_base(owner_client) + "/comments", json={"body": "del"}).json()
    resp = owner_client.delete(f"/api/v1/comments/{c['id']}")
    assert resp.status_code == 200
    assert owner_client.get(_base(owner_client) + "/comments").json() == []


def test_non_member_cannot_comment(owner_client):
    _publish(owner_client)
    with TestClient(app) as other:
        _register(other, f"x-{uuid.uuid4().hex[:6]}@example.com")
        resp = other.post(_base(owner_client) + "/comments", json={"body": "hi"})
        assert resp.status_code == 403


def test_anonymous_cannot_comment(owner_client):
    _publish(owner_client, slug="pub", visibility="public")
    with TestClient(app) as anon:
        resp = anon.post(_base(owner_client, "pub") + "/comments", json={"body": "hi"})
        assert resp.status_code == 401


def test_logged_in_non_member_can_comment_on_public(owner_client):
    _publish(owner_client, slug="pub", visibility="public")
    with TestClient(app) as other:
        _register(other, f"pub-{uuid.uuid4().hex[:6]}@example.com", name="Reader")
        resp = other.post(
            _base(owner_client, "pub") + "/comments", json={"body": "great read"}
        )
        assert resp.status_code == 200, resp.text
        # ...and can read the thread back.
        listed = other.get(_base(owner_client, "pub") + "/comments").json()
        assert len(listed) == 1
        # ...but cannot moderate (resolve stays members-only).
        cid = resp.json()["id"]
        assert other.post(f"/api/v1/comments/{cid}/resolve").status_code == 403


def test_logged_in_non_member_can_comment_via_share_token(owner_client):
    _publish(owner_client, slug="priv", visibility="private")
    created = owner_client.post(
        _base(owner_client, "priv") + "/share-links", json={"access_type": "latest"}
    )
    assert created.status_code in (200, 201), created.text
    token = created.json()["share_url"].rsplit("/share/", 1)[1]

    with TestClient(app) as other:
        _register(other, f"shr-{uuid.uuid4().hex[:6]}@example.com")
        base = _base(owner_client, "priv") + "/comments"
        # Without the token, a non-member is blocked from the private page.
        assert other.post(base, json={"body": "no"}).status_code == 403
        # With a valid share token, commenting is allowed.
        ok = other.post(base + f"?share_token={token}", json={"body": "via share"})
        assert ok.status_code == 200, ok.text

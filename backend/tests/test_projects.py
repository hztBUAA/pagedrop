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
        _register(c, f"pub-{uuid.uuid4().hex[:8]}@example.com", name="Publisher")
        ws = c.get("/api/v1/workspaces").json()[0]
        c.workspace_slug = ws["slug"]
        yield c


def _publish(client, slug="report", title="Report", content="# Hello", **kw):
    body = {
        "workspace_slug": client.workspace_slug,
        "slug": slug,
        "title": title,
        "content_type": "markdown",
        "content": content,
        "visibility": "unlisted",
    }
    body.update(kw)
    return client.post("/api/v1/projects.publish", json=body)


def test_publish_creates_project_v1(owner_client):
    resp = _publish(owner_client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == 1
    assert body["latest_url"].endswith(f"/p/{owner_client.workspace_slug}/report")
    assert body["version_url"].endswith(f"/p/{owner_client.workspace_slug}/report/v/1")


def test_publish_second_version_increments(owner_client):
    _publish(owner_client, slug="doc", content="v1")
    resp = _publish(owner_client, slug="doc", content="v2", message="update")
    assert resp.json()["version"] == 2

    versions = owner_client.get(
        f"/api/v1/projects/{owner_client.workspace_slug}/doc/versions"
    ).json()
    assert [v["version_number"] for v in versions] == [2, 1]


def test_old_version_immutable(owner_client):
    _publish(owner_client, slug="imm", content="original")
    _publish(owner_client, slug="imm", content="changed")
    v1 = owner_client.get(
        f"/api/v1/projects/{owner_client.workspace_slug}/imm/versions/1"
    ).json()
    assert v1["source_content"] == "original"


def test_latest_points_to_newest(owner_client):
    _publish(owner_client, slug="lt", content="one")
    _publish(owner_client, slug="lt", content="two")
    latest = owner_client.get(
        f"/api/v1/public/projects/{owner_client.workspace_slug}/lt/latest"
    ).json()
    assert latest["source_content"] == "two"
    assert latest["version_number"] == 2
    assert latest["is_latest"] is True


def test_safe_html_sanitized(owner_client):
    _publish(
        owner_client,
        slug="htmlpage",
        content='<p>ok</p><script>alert(1)</script>',
        content_type="safe_html",
    )
    ver = owner_client.get(
        f"/api/v1/projects/{owner_client.workspace_slug}/htmlpage/versions/1"
    ).json()
    assert "<script>" not in (ver["rendered_html"] or "")
    assert "ok" in ver["rendered_html"]


def test_safe_html_keeps_pagedrop_asset_scheme(owner_client):
    # The pagedrop:// image scheme must survive sanitization so the frontend
    # can resolve it to a real asset URL; javascript: must still be stripped.
    _publish(
        owner_client,
        slug="imghtml",
        content='<img src="pagedrop://asset/abc123de"><img src="javascript:alert(1)">',
        content_type="safe_html",
    )
    ver = owner_client.get(
        f"/api/v1/projects/{owner_client.workspace_slug}/imghtml/versions/1"
    ).json()
    html = ver["rendered_html"] or ""
    assert "pagedrop://asset/abc123de" in html
    assert "javascript:" not in html


def test_secret_scan_blocks_publish(owner_client):
    resp = _publish(
        owner_client,
        slug="leaky",
        content="config\nOPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456\n",
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error"] == "secret_detected"
    assert len(detail["findings"]) >= 1
    # full secret must not be echoed
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in resp.text


def test_secret_scan_force_override(owner_client):
    resp = _publish(
        owner_client,
        slug="forced",
        content="AWS key AKIAIOSFODNN7EXAMPLE here",
        force=True,
    )
    assert resp.status_code == 200
    assert resp.json()["secret_scan_status"] == "overridden"


def test_private_project_cross_user_denied(owner_client):
    _publish(owner_client, slug="secretdoc", visibility="private", content="top secret")

    with TestClient(app) as other:
        _register(other, "intruder@example.com")
        resp = other.get(
            f"/api/v1/public/projects/{owner_client.workspace_slug}/secretdoc/latest"
        )
        assert resp.status_code == 404

    # anonymous also denied
    with TestClient(app) as anon:
        resp = anon.get(
            f"/api/v1/public/projects/{owner_client.workspace_slug}/secretdoc/latest"
        )
        assert resp.status_code == 404


def test_unlisted_accessible_and_noindex(owner_client):
    _publish(owner_client, slug="unl", visibility="unlisted", content="hi")
    with TestClient(app) as anon:
        resp = anon.get(
            f"/api/v1/public/projects/{owner_client.workspace_slug}/unl/latest"
        )
        assert resp.status_code == 200
        assert resp.json()["noindex"] is True

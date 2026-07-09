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


def _workspace_id(client):
    return client.get("/api/v1/workspaces").json()[0]["id"]


def test_list_projects_search_and_pagination(owner_client):
    _publish(owner_client, slug="alpha", title="Alpha Report")
    _publish(owner_client, slug="beta", title="Beta Notes")
    _publish(owner_client, slug="gamma", title="Gamma Alpha")
    ws_id = _workspace_id(owner_client)

    all_p = owner_client.get(f"/api/v1/projects?workspace_id={ws_id}").json()
    assert len(all_p) == 3

    # Search matches title or slug, case-insensitive.
    found = owner_client.get(f"/api/v1/projects?workspace_id={ws_id}&q=alpha").json()
    assert {p["slug"] for p in found} == {"alpha", "gamma"}

    # Pagination.
    page = owner_client.get(f"/api/v1/projects?workspace_id={ws_id}&limit=2&offset=0").json()
    assert len(page) == 2
    page2 = owner_client.get(f"/api/v1/projects?workspace_id={ws_id}&limit=2&offset=2").json()
    assert len(page2) == 1


def test_list_projects_requires_workspace_for_session_user(owner_client):
    resp = owner_client.get("/api/v1/projects")
    assert resp.status_code == 422


def test_list_projects_with_api_token(owner_client):
    _publish(owner_client, slug="tokvisible", title="Token Visible")
    tok = owner_client.post(
        "/api/v1/tokens",
        json={
            "workspace_slug": owner_client.workspace_slug,
            "name": "lister",
            "scopes": ["projects:read"],
        },
    ).json()["token"]

    # Token needs no workspace_id (bound to its workspace) and lists projects.
    resp = owner_client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {tok}"}
    )
    assert resp.status_code == 200, resp.text
    assert any(p["slug"] == "tokvisible" for p in resp.json())


def test_list_projects_token_allowlist_filters(owner_client):
    _publish(owner_client, slug="allowed", title="Allowed")
    _publish(owner_client, slug="hidden", title="Hidden")
    tok = owner_client.post(
        "/api/v1/tokens",
        json={
            "workspace_slug": owner_client.workspace_slug,
            "name": "scoped",
            "scopes": ["projects:read"],
            "project_allowlist": ["allowed"],
        },
    ).json()["token"]

    resp = owner_client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {tok}"}
    )
    slugs = {p["slug"] for p in resp.json()}
    assert "allowed" in slugs and "hidden" not in slugs


def test_publish_stores_and_normalizes_folder_path(owner_client):
    resp = _publish(owner_client, slug="infra-doc", folder_path="/ops/pagedrop/")
    assert resp.status_code == 200, resp.text
    proj = owner_client.get(
        f"/api/v1/projects/{owner_client.workspace_slug}/infra-doc"
    ).json()
    # Leading/trailing slashes are trimmed on the way in.
    assert proj["folder_path"] == "ops/pagedrop"


def test_folder_filter_matches_folder_and_descendants(owner_client):
    _publish(owner_client, slug="root-doc", title="Root")
    _publish(owner_client, slug="ops-a", title="A", folder_path="ops")
    _publish(owner_client, slug="ops-b", title="B", folder_path="ops/pagedrop")
    _publish(owner_client, slug="hr-a", title="HR", folder_path="hr")
    ws_id = _workspace_id(owner_client)

    got = owner_client.get(f"/api/v1/projects?workspace_id={ws_id}&folder=ops").json()
    assert {p["slug"] for p in got} == {"ops-a", "ops-b"}

    nested = owner_client.get(
        f"/api/v1/projects?workspace_id={ws_id}&folder=ops/pagedrop"
    ).json()
    assert {p["slug"] for p in nested} == {"ops-b"}


def test_list_folders_returns_distinct_paths(owner_client):
    _publish(owner_client, slug="d1", folder_path="ops")
    _publish(owner_client, slug="d2", folder_path="ops/pagedrop")
    _publish(owner_client, slug="d3", folder_path="ops")
    _publish(owner_client, slug="d4")  # no folder
    ws_id = _workspace_id(owner_client)

    folders = owner_client.get(f"/api/v1/projects/folders?workspace_id={ws_id}").json()
    assert folders == ["ops", "ops/pagedrop"]


def test_archive_hides_from_default_list_and_unarchive_restores(owner_client):
    _publish(owner_client, slug="active-doc", title="Active")
    _publish(owner_client, slug="to-archive", title="Archive Me")
    ws_id = _workspace_id(owner_client)
    ws = owner_client.workspace_slug

    assert owner_client.post(f"/api/v1/projects/{ws}/to-archive/archive").status_code == 200

    active = owner_client.get(f"/api/v1/projects?workspace_id={ws_id}").json()
    assert {p["slug"] for p in active} == {"active-doc"}

    archived = owner_client.get(
        f"/api/v1/projects?workspace_id={ws_id}&status=archived"
    ).json()
    assert {p["slug"] for p in archived} == {"to-archive"}

    all_p = owner_client.get(f"/api/v1/projects?workspace_id={ws_id}&status=all").json()
    assert {p["slug"] for p in all_p} == {"active-doc", "to-archive"}

    assert owner_client.post(f"/api/v1/projects/{ws}/to-archive/unarchive").status_code == 200
    restored = owner_client.get(f"/api/v1/projects?workspace_id={ws_id}").json()
    assert {p["slug"] for p in restored} == {"active-doc", "to-archive"}


def test_soft_delete_removes_from_list_and_public(owner_client):
    _publish(owner_client, slug="doomed", title="Doomed", visibility="public")
    ws_id = _workspace_id(owner_client)
    ws = owner_client.workspace_slug

    assert owner_client.delete(f"/api/v1/projects/{ws}/doomed").status_code == 200

    # Gone from every status view (soft-deleted rows are excluded outright).
    for status in ("active", "archived", "all"):
        got = owner_client.get(
            f"/api/v1/projects?workspace_id={ws_id}&status={status}"
        ).json()
        assert all(p["slug"] != "doomed" for p in got)

    # And no longer publicly reachable by direct URL.
    with TestClient(app) as anon:
        resp = anon.get(f"/api/v1/public/projects/{ws}/doomed/latest")
        assert resp.status_code == 404



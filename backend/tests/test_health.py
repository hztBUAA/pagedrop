def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "PageDrop"


def test_all_tables_registered():
    from app.core.database import Base

    tables = set(Base.metadata.tables)
    assert tables == {
        "users",
        "workspaces",
        "workspace_members",
        "projects",
        "page_versions",
        "api_tokens",
        "share_links",
        "audit_logs",
        "verification_codes",
        "assets",
        "comments",
        "oauth_identities",
    }

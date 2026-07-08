from tests.conftest import issue_register_code as _issue_code


def register(client, email, password="password123", name=None):
    code = _issue_code(email, "register")
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "name": name, "code": code},
    )


def test_register_requires_valid_code(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "nocode@example.com", "password": "password123", "code": "000000"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_code"


def test_reset_password_flow(client):
    register(client, "reset@example.com", password="oldpass123")
    client.post("/api/v1/auth/logout")

    code = _issue_code("reset@example.com", "reset")
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"email": "reset@example.com", "code": code, "new_password": "newpass456"},
    )
    assert resp.status_code == 200
    client.post("/api/v1/auth/logout")

    # old password rejected, new password works
    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "oldpass123"},
    )
    assert bad.status_code == 401
    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "newpass456"},
    )
    assert ok.status_code == 200


def test_register_creates_user_and_personal_workspace(client):
    resp = register(client, "alice@example.com", name="Alice")
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"

    # session cookie should be set; /me works
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"

    # personal workspace auto-created with owner role
    ws = client.get("/api/v1/workspaces")
    assert ws.status_code == 200
    workspaces = ws.json()
    assert len(workspaces) == 1
    assert workspaces[0]["type"] == "personal"
    assert workspaces[0]["role"] == "owner"


def test_duplicate_email_rejected(client):
    register(client, "dup@example.com")
    resp = register(client, "dup@example.com")
    assert resp.status_code == 409


def test_login_and_logout(client):
    register(client, "bob@example.com", password="secretpass")
    client.post("/api/v1/auth/logout")
    # after logout, /me is unauthorized
    assert client.get("/api/v1/auth/me").status_code == 401

    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "secretpass"},
    )
    assert ok.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200

    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "wrong"},
    )
    assert bad.status_code == 401


def test_unauthenticated_me(client):
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cross_user_workspace_isolation(client):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as ca:
        register(ca, "user_a@example.com")
        wa = ca.get("/api/v1/workspaces").json()
        a_ws_id = wa[0]["id"]

    with TestClient(app) as cb:
        register(cb, "user_b@example.com")
        # user B cannot view user A's workspace
        resp = cb.get(f"/api/v1/workspaces/{a_ws_id}")
        assert resp.status_code == 403


def test_whoami_session_user(client):
    register(client, "who@example.com", name="Who")
    resp = client.get("/api/v1/auth/whoami")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "user"
    assert body["email"] == "who@example.com"
    assert body["token_id"] is None
    # session users carry full scopes
    assert "projects:write" in body["scopes"]


def test_login_rate_limited(client):
    register(client, "rl@example.com", password="secretpass")
    # login bucket allows 10/min; the 11th within the window is throttled
    last = None
    for _ in range(11):
        last = client.post(
            "/api/v1/auth/login",
            json={"email": "rl@example.com", "password": "wrong"},
        )
    assert last.status_code == 429
    assert last.json()["detail"] == "rate_limited"

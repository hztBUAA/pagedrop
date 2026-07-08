import pytest

from app.services import github_oauth_service
from app.services.github_oauth_service import GithubIdentity
from tests.test_auth import register


def _fake_identity(**kwargs):
    base = dict(id="12345", login="octocat", email="octocat@example.com", name="Octo Cat")
    base.update(kwargs)
    return GithubIdentity(**base)


@pytest.fixture
def patch_github(monkeypatch):
    """Return a setter so each test controls the identity the 'GitHub token' maps to."""

    def _set(identity: GithubIdentity | None):
        def _fetch(access_token: str):
            if identity is None:
                raise github_oauth_service.GithubOAuthError("invalid_github_token")
            return identity

        monkeypatch.setattr(github_oauth_service, "fetch_github_identity", _fetch)

    return _set


def test_github_new_user_creates_account_and_workspace(client, patch_github):
    patch_github(_fake_identity())
    resp = client.post("/api/v1/auth/github", json={"access_token": "gho_x"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "octocat@example.com"

    # session established
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200

    # personal workspace auto-created
    ws = client.get("/api/v1/workspaces").json()
    assert len(ws) == 1
    assert ws[0]["type"] == "personal"
    assert ws[0]["role"] == "owner"


def test_github_repeat_login_reuses_account(client, patch_github):
    patch_github(_fake_identity(id="777", email="repeat@example.com"))
    first = client.post("/api/v1/auth/github", json={"access_token": "gho_x"})
    client.post("/api/v1/auth/logout")
    second = client.post("/api/v1/auth/github", json={"access_token": "gho_y"})
    assert first.json()["id"] == second.json()["id"]


def test_github_links_existing_email_account(client, patch_github):
    # Pre-existing password account.
    register(client, "linkme@example.com", password="password123", name="Linker")
    client.post("/api/v1/auth/logout")

    patch_github(_fake_identity(id="999", email="linkme@example.com", login="linker"))
    resp = client.post("/api/v1/auth/github", json={"access_token": "gho_x"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "linkme@example.com"

    # linked onto the same account — no duplicate workspace created
    ws = client.get("/api/v1/workspaces").json()
    assert len(ws) == 1

    from app.core.database import SessionLocal
    from app.models.oauth_identity import OAuthIdentity
    from app.services import auth_service

    db = SessionLocal()
    try:
        user = auth_service.get_user_by_email(db, "linkme@example.com")
        identity = (
            db.query(OAuthIdentity)
            .filter_by(provider="github", user_id=user.id)
            .one()
        )
        assert identity.provider_account_id == "999"
        assert identity.provider_login == "linker"
    finally:
        db.close()


def test_github_invalid_token_rejected(client, patch_github):
    patch_github(None)
    resp = client.post("/api/v1/auth/github", json={"access_token": "bad"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_github_token"

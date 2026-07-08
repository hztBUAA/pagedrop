"""Web authorization-code OAuth flow (GET start → POST callback)."""
from urllib.parse import parse_qs, urlparse

import pytest

from app.services import oauth_providers
from app.services.oauth_providers import ProviderIdentity
from tests.test_auth import register


@pytest.fixture
def enable_github(monkeypatch):
    monkeypatch.setattr(oauth_providers.settings, "github_client_id", "gh-client")
    monkeypatch.setattr(oauth_providers.settings, "github_client_secret", "gh-secret")


@pytest.fixture
def patch_exchange(monkeypatch):
    """Control the identity a callback resolves to, bypassing the network."""

    def _set(identity: ProviderIdentity | None):
        def _exchange(provider, *, code, code_verifier=None):
            if identity is None:
                raise oauth_providers.OAuthProviderError("code_exchange_failed")
            return identity

        monkeypatch.setattr(oauth_providers, "exchange_and_fetch_identity", _exchange)

    return _set


def _identity(**kwargs):
    base = dict(
        provider="github",
        account_id="55555",
        login="webcat",
        email="webcat@example.com",
        name="Web Cat",
    )
    base.update(kwargs)
    return ProviderIdentity(**base)


def _start_and_state(client, provider="github"):
    resp = client.get(f"/api/v1/auth/oauth/{provider}/start")
    assert resp.status_code == 200
    url = resp.json()["authorize_url"]
    return parse_qs(urlparse(url).query)["state"][0]


def test_providers_list_reflects_config(client, enable_github):
    resp = client.get("/api/v1/auth/oauth/providers")
    assert resp.status_code == 200
    assert resp.json()["providers"] == ["github"]


def test_start_disabled_provider_404(client):
    # No credentials configured → provider disabled.
    resp = client.get("/api/v1/auth/oauth/github/start")
    assert resp.status_code == 404


def test_web_callback_new_user(client, enable_github, patch_exchange):
    patch_exchange(_identity())
    state = _start_and_state(client)
    resp = client.post("/api/v1/auth/oauth/callback", json={"code": "abc", "state": state})
    assert resp.status_code == 200
    assert resp.json()["email"] == "webcat@example.com"

    ws = client.get("/api/v1/workspaces").json()
    assert len(ws) == 1
    assert ws[0]["type"] == "personal"


def test_web_callback_links_existing_email(client, enable_github, patch_exchange):
    register(client, "weblink@example.com", password="password123", name="WL")
    client.post("/api/v1/auth/logout")

    patch_exchange(_identity(account_id="888", email="weblink@example.com", login="wl"))
    state = _start_and_state(client)
    resp = client.post("/api/v1/auth/oauth/callback", json={"code": "abc", "state": state})
    assert resp.status_code == 200
    assert resp.json()["email"] == "weblink@example.com"
    ws = client.get("/api/v1/workspaces").json()
    assert len(ws) == 1


def test_web_callback_bad_state_rejected(client, enable_github, patch_exchange):
    patch_exchange(_identity())
    _start_and_state(client)  # sets a valid cookie
    resp = client.post(
        "/api/v1/auth/oauth/callback", json={"code": "abc", "state": "not-the-nonce"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_state"


def test_web_callback_no_state_cookie_rejected(client, enable_github, patch_exchange):
    patch_exchange(_identity())
    # Never call start → no pd_oauth_state cookie present.
    client.cookies.clear()
    resp = client.post(
        "/api/v1/auth/oauth/callback", json={"code": "abc", "state": "anything"}
    )
    assert resp.status_code == 400

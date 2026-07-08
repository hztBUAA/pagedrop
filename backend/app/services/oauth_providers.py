"""OAuth provider registry for the web authorization-code flow.

Each provider knows how to (1) build its authorize URL, (2) exchange an auth
code for an access token, and (3) fetch the user's identity. GitHub identity
resolution is shared with the CLI device flow via ``github_oauth_service``.

A provider is *enabled* only when both its client_id and client_secret are set,
so leaving Google credentials blank simply hides it everywhere.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services import github_oauth_service

PROVIDERS = ("github", "google")


class OAuthProviderError(Exception):
    """Raised for unknown/disabled providers or failed token/identity exchange."""


@dataclass
class ProviderIdentity:
    provider: str
    account_id: str
    login: str
    email: str
    name: str | None


def _credentials(provider: str) -> tuple[str, str]:
    if provider == "github":
        return settings.github_client_id, settings.github_client_secret
    if provider == "google":
        return settings.google_client_id, settings.google_client_secret
    raise OAuthProviderError("unknown_provider")


def is_enabled(provider: str) -> bool:
    if provider not in PROVIDERS:
        return False
    client_id, client_secret = _credentials(provider)
    return bool(client_id and client_secret)


def enabled_providers() -> list[str]:
    return [p for p in PROVIDERS if is_enabled(p)]


def uses_pkce(provider: str) -> bool:
    return provider == "google"


def generate_pkce() -> tuple[str, str]:
    """Return (verifier, S256 challenge) for the PKCE extension (Google)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def build_authorize_url(provider: str, *, state: str, code_challenge: str | None = None) -> str:
    if not is_enabled(provider):
        raise OAuthProviderError("provider_disabled")
    client_id, _ = _credentials(provider)
    if provider == "github":
        params = {
            "client_id": client_id,
            "redirect_uri": settings.oauth_redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return f"{settings.github_oauth_base.rstrip('/')}/login/oauth/authorize?{urlencode(params)}"
    # google
    params = {
        "client_id": client_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "include_granted_scopes": "true",
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return f"{settings.google_authorize_base.rstrip('/')}/o/oauth2/v2/auth?{urlencode(params)}"


def _exchange_github(code: str, client_id: str, client_secret: str) -> str:
    url = f"{settings.github_oauth_base.rstrip('/')}/login/oauth/access_token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": settings.oauth_redirect_uri,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, data=data, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise OAuthProviderError("provider_unreachable") from exc
    if resp.status_code != 200:
        raise OAuthProviderError("code_exchange_failed")
    token = resp.json().get("access_token")
    if not token:
        raise OAuthProviderError("code_exchange_failed")
    return token


def _exchange_google(
    code: str, client_id: str, client_secret: str, code_verifier: str | None
) -> str:
    url = f"{settings.google_oauth_base.rstrip('/')}/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": settings.oauth_redirect_uri,
        "grant_type": "authorization_code",
    }
    if code_verifier:
        data["code_verifier"] = code_verifier
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, data=data, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise OAuthProviderError("provider_unreachable") from exc
    if resp.status_code != 200:
        raise OAuthProviderError("code_exchange_failed")
    token = resp.json().get("access_token")
    if not token:
        raise OAuthProviderError("code_exchange_failed")
    return token


def _fetch_google_identity(access_token: str) -> ProviderIdentity:
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                settings.google_userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        raise OAuthProviderError("provider_unreachable") from exc
    if resp.status_code != 200:
        raise OAuthProviderError("invalid_google_token")
    info = resp.json()
    email = info.get("email")
    if not email or not info.get("email_verified", False):
        raise OAuthProviderError("no_verified_email")
    return ProviderIdentity(
        provider="google",
        account_id=str(info["sub"]),
        login=email,
        email=email,
        name=info.get("name"),
    )


def exchange_and_fetch_identity(
    provider: str, *, code: str, code_verifier: str | None = None
) -> ProviderIdentity:
    """Exchange an authorization code and return the resolved identity."""
    if not is_enabled(provider):
        raise OAuthProviderError("provider_disabled")
    client_id, client_secret = _credentials(provider)
    if provider == "github":
        access_token = _exchange_github(code, client_id, client_secret)
        try:
            gh = github_oauth_service.fetch_github_identity(access_token)
        except github_oauth_service.GithubOAuthError as exc:
            raise OAuthProviderError(str(exc)) from exc
        return ProviderIdentity(
            provider="github",
            account_id=gh.id,
            login=gh.login,
            email=gh.email,
            name=gh.name,
        )
    # google
    access_token = _exchange_google(code, client_id, client_secret, code_verifier)
    return _fetch_google_identity(access_token)

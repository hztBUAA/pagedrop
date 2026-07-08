"""Verify a GitHub OAuth access token and extract the user's identity.

The CLI performs the OAuth *device flow* directly against github.com (public
client_id, no secret) and sends us the resulting access token. We trust it only
to read the identity it belongs to via the GitHub API.
"""
from dataclasses import dataclass

import httpx

from app.core.config import settings


class GithubOAuthError(Exception):
    """Raised when the GitHub token is invalid or no usable email is available."""


@dataclass
class GithubIdentity:
    id: str
    login: str
    email: str
    name: str | None


def _pick_email(user: dict, emails: list[dict]) -> str | None:
    # Prefer a primary + verified email; fall back to any verified one.
    verified = [e for e in emails if e.get("verified")]
    for e in verified:
        if e.get("primary"):
            return e["email"]
    if verified:
        return verified[0]["email"]
    # Some accounts expose a public email directly on the profile.
    return user.get("email")


def fetch_github_identity(access_token: str) -> GithubIdentity:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = settings.github_api_base.rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            user_resp = client.get(f"{base}/user", headers=headers)
            if user_resp.status_code != 200:
                raise GithubOAuthError("invalid_github_token")
            user = user_resp.json()
            emails_resp = client.get(f"{base}/user/emails", headers=headers)
            emails = emails_resp.json() if emails_resp.status_code == 200 else []
    except httpx.HTTPError as exc:
        raise GithubOAuthError("github_unreachable") from exc

    if not isinstance(emails, list):
        emails = []
    email = _pick_email(user, emails)
    if not email:
        raise GithubOAuthError("no_verified_email")

    return GithubIdentity(
        id=str(user["id"]),
        login=user.get("login") or "",
        email=email,
        name=user.get("name"),
    )

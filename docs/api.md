# PageDrop HTTP API

Base URL: `https://pagedrop.justinhuang.top/api/v1`

Two authentication methods:

- **Session cookie** (`pd_session`, httpOnly) — set by `/auth/login` and
  `/auth/register`. Used by the web app. Send with `credentials: include`.
- **API token** (`Authorization: Bearer pd_live_...`) — for CLI/agents. Tokens
  are workspace-scoped, carry an explicit scope set, and may be restricted to a
  project allowlist. The plaintext is shown only once at creation.

Scopes: `projects:read`, `projects:write`, `versions:read`, `versions:write`,
`assets:write`, `share_links:create`, `tokens:read`.

## Auth

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| POST | `/auth/register` | none | `{email, password, name?}` → sets cookie, creates personal workspace |
| POST | `/auth/login` | none | `{email, password}` → sets cookie |
| POST | `/auth/logout` | cookie | clears cookie |
| GET | `/auth/me` | cookie | current user |
| GET | `/auth/whoami` | cookie or token | actor introspection: `{type, user_id, email, token_id, token_name, workspace_id, scopes}` |

Rate limits: register 5/min, login 10/min (429 `rate_limited` on exceed).

## Workspaces

| Method | Path | Auth |
| --- | --- | --- |
| GET | `/workspaces` | cookie |
| POST | `/workspaces` | cookie |
| GET | `/workspaces/{id}` | cookie (member) |
| GET | `/workspaces/{id}/members` | cookie (member) |
| POST | `/workspaces/{id}/members` | cookie (admin+) |

## Projects & versions

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/projects.publish` | cookie (editor+) or token (`versions:write`) |
| GET | `/projects?workspace_id=` | cookie |
| GET | `/projects/{ws}/{slug}` | cookie or token (`projects:read`) |
| GET | `/projects/{ws}/{slug}/versions` | cookie or token (`versions:read`) |
| GET | `/projects/{ws}/{slug}/versions/{n}` | cookie or token (`versions:read`) |
| PATCH | `/projects/{ws}/{slug}/settings` | cookie (admin+) |

**Publish body:**

```json
{
  "workspace_slug": "my-ws",
  "slug": "release-notes",
  "title": "Release Notes",
  "content_type": "markdown",     // markdown | safe_html | sandbox_html
  "content": "# Hello",
  "visibility": "unlisted",         // public | unlisted | private
  "message": "changelog text",     // optional
  "summary": "short summary",      // optional
  "source": "agent",               // web | agent | cli | api
  "force": false                     // override secret-scan block
}
```

Each publish creates a **new immutable version**; existing versions are never
overwritten. Rate limit: 30/min.

**Secret scan:** if secrets are detected the response is `400` with
`{"detail": {"error": "secret_detected", "findings": [{type, preview}]}}`. Only
masked previews are returned — never full secret values. Set `"force": true` to
publish anyway.

## Share links

| Method | Path | Auth |
| --- | --- | --- |
| GET | `/projects/{ws}/{slug}/share-links` | cookie (admin+) |
| POST | `/projects/{ws}/{slug}/share-links` | cookie (admin+) or token (`share_links:create`) |
| DELETE | `/share-links/{id}` | cookie (admin+) |

Create body: `{access_type: "latest"|"fixed_version", version?, password?,
expires_at?, max_views?}`. Response includes the one-time `share_url`
(`pds_...` token).

## API tokens

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/tokens` | cookie (admin+) |
| GET | `/tokens?workspace_id=` | cookie (admin+) |
| DELETE | `/tokens/{id}` | cookie (admin+) |

Create returns the plaintext token **once**; listings return only the prefix and
metadata. Rate limit: 10/min.

## Public (no auth)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/public/projects/{ws}/{slug}/latest` | public/unlisted only |
| GET | `/public/projects/{ws}/{slug}/versions/{n}` | |
| GET | `/public/share/{token}` | password-protected → `401` until verified |
| POST | `/public/share/{token}/verify-password` | `{password}`, 10/min |

Unlisted, private, and share pages are served with `noindex`.

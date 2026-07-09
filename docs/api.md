# PageDrop HTTP API

Base URL: `https://pagedrop.justinhuang.top/api/v1`

Two authentication methods:

- **Session cookie** (`pd_session`, httpOnly) — set by `/auth/login` and
  `/auth/register`. Used by the web app. Send with `credentials: include`.
- **API token** (`Authorization: Bearer pd_live_...`) — for CLI/agents. Tokens
  are workspace-scoped, carry an explicit scope set, and may be restricted to a
  project allowlist. The plaintext is shown only once at creation.

Scopes: `projects:read`, `projects:write`, `versions:read`, `versions:write`,
`assets:write`, `comments:read`, `comments:write`, `share_links:create`,
`tokens:read`.

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

## Visibility & sharing model

Every project has a `visibility` of `public`, `unlisted`, or `private`. All
access decisions go through one function — `can_view_project`
(`backend/app/permissions/service.py`):

| Visibility | Who can view via the canonical URL | Search engines |
| --- | --- | --- |
| `public` | anyone with the link, including anonymous | indexable |
| `unlisted` | anyone with the link, including anonymous | `noindex` |
| `private` | workspace members / platform admins only (anonymous → `404`) | `noindex` |

Two things commonly trip people up:

- **`unlisted` is fully shareable.** `can_view_project` only restricts
  `private`; `public` and `unlisted` are both served to anyone who has the link.
  The *only* behavioral difference between `public` and `unlisted` is the
  `noindex` meta tag (`public.py`: `noindex = visibility != "public"`, applied by
  the web app). There is no public directory or listing page, so "unlisted"
  effectively means "public but not indexed / not advertised."
- **Share links bypass visibility entirely.** `GET /public/share/{token}` does
  **not** call `can_view_project` — the share token (plus an optional password)
  is the sole gate. This is how a `private` page can still be handed to an
  outside viewer: create a share link rather than flipping the project to
  public. Share links also carry optional expiry, password, and max-view limits.

Note that the public *asset* endpoint (`/public/assets/{id}`) still enforces
`can_view_project`, so images on a `private` page shared by link will not load
unless the viewer is a workspace member. Prefer `unlisted` for link-sharing
pages that contain images.

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

## Assets (images)

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/assets` | cookie (editor+) or token (`assets:write`) |
| GET | `/assets/{id}` | cookie (project/workspace access) or token (`versions:read`) |

`POST /assets` is `multipart/form-data`: `file` (png/jpeg/webp/gif, ≤10 MB),
`workspace_slug`, optional `project_slug`. Response includes `ref`
(`pagedrop://asset/<id>`) — embed this in Markdown/HTML content. Uploads are
content-addressed (deduped by sha256 within a workspace). Rate limit: 60/min.

Reference images in content via the `pagedrop://asset/<id>` scheme. On publish,
any workspace-scoped assets referenced by the content are attached to the
project so they render on its public page. Clients resolve the scheme to
`/assets/<id>` (authed) or `/public/assets/<id>` (public) at render time.

## Comments

| Method | Path | Auth |
| --- | --- | --- |
| GET | `/projects/{ws}/{slug}/comments?status=` | cookie (viewer+) or token (`comments:read`) |
| POST | `/projects/{ws}/{slug}/comments` | cookie (member) or token (`comments:write`) |
| POST | `/comments/{id}/resolve` | cookie (member) or token (`comments:write`) |
| POST | `/comments/{id}/reopen` | cookie (member) or token (`comments:write`) |
| DELETE | `/comments/{id}` | cookie (member) or token (`comments:write`) |

Comments are **project-scoped** (they survive version iteration). Create body:
`{body, thread_root_id?, anchor_version_number?, anchor_quote?, anchor_prefix?,
anchor_suffix?}`. Passing `thread_root_id` makes the comment a reply. `status`
filter is `open` | `resolved` (replies of matching roots are included). Token
authors display as `agent:<token-name>`.

## Public (no auth)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/public/projects/{ws}/{slug}/latest` | public/unlisted only |
| GET | `/public/projects/{ws}/{slug}/versions/{n}` | |
| GET | `/public/assets/{id}` | only assets of a viewable project |
| GET | `/public/share/{token}` | password-protected → `401` until verified |
| POST | `/public/share/{token}/verify-password` | `{password}`, 10/min |

Unlisted, private, and share pages are served with `noindex`.

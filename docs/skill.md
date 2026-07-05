# PageDrop Agent Skill

This guide lets an AI agent publish artifacts (reports, dashboards, docs,
diagrams) to PageDrop and share them with a stable URL. PageDrop renders
Markdown (with GFM, math, syntax highlighting, and Mermaid) and sanitized HTML,
and is mobile-friendly.

## When to use PageDrop

Use it whenever you produce content a human will read in a browser and you want
a durable, shareable link instead of dumping a wall of text into chat:

- Analysis write-ups, run reports, changelogs, meeting notes
- Rendered dashboards / static HTML
- Anything you'll iterate on — each publish is a new immutable version

## Setup (once)

1. The human creates a **workspace-scoped API token** in the PageDrop web app
   and grants only the scopes you need — for publishing: `versions:write`
   (add `versions:read` / `share_links:create` if you'll list versions or
   create share links). Optionally restrict it to specific project slugs.
2. Store the token securely. Never print it back or commit it.

## Publishing

### Via CLI (recommended)

```bash
pagedrop login --token "$PAGEDROP_TOKEN" --url https://pagedrop.justinhuang.top
generate_report_markdown | pagedrop publish - \
  -w <workspace-slug> -s daily-report -T "Daily Report" -m "run 2026-07-06"
```

Or with environment variables only (no stored config), ideal for automation:

```bash
export PAGEDROP_TOKEN=pd_live_xxx
export PAGEDROP_URL=https://pagedrop.justinhuang.top
echo "# Report" | pagedrop publish - -w my-ws -s report
```

### Via HTTP

```bash
curl -X POST https://pagedrop.justinhuang.top/api/v1/projects.publish \
  -H "Authorization: Bearer $PAGEDROP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_slug": "my-ws",
    "slug": "daily-report",
    "title": "Daily Report",
    "content_type": "markdown",
    "content": "# Results\n\n- item 1\n- item 2",
    "visibility": "unlisted",
    "source": "agent"
  }'
```

The response contains `latest_url` and `version_url` — return the `latest_url`
to the human.

## Rules an agent must follow

1. **Never publish secrets.** PageDrop scans content and blocks publishes that
   contain obvious credentials (API keys, tokens, private keys). If you get a
   `secret_detected` error, remove the secret and re-publish — do **not** blindly
   set `force: true`. Only override if you are certain it is a false positive.
2. **Pick the right visibility.** Default to `unlisted` (link-only, `noindex`).
   Use `public` only when the human wants it indexable. Use `private` for
   workspace-members-only.
3. **Choose the content type deliberately.**
   - `markdown` — default; safest and richest for reports.
   - `safe_html` — server-sanitized HTML (scripts stripped).
   - `sandbox_html` — arbitrary HTML rendered in a locked-down iframe with **no
     script execution** and treated as an opaque origin (no access to the parent
     page, cookies, or storage). Use only when you truly need raw HTML.
4. **Versions are immutable.** Re-publishing the same slug creates a new version;
   it never overwrites history. Put a short changelog in `message`.
5. **Respect token scope.** A token is bound to one workspace and may be limited
   to certain project slugs. Don't attempt to publish outside its allowlist.
6. **Sharing:** to give a time-limited or password-protected link, create a share
   link (`share_links:create` scope) rather than making the page public.

## Verifying your credential

```bash
pagedrop whoami          # or: GET /api/v1/auth/whoami with the Bearer token
```

Returns the token's workspace and granted scopes, so you can confirm what you're
allowed to do before publishing.

See `docs/api.md` for the full API and `docs/cli.md` for all CLI commands.

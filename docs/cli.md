# PageDrop CLI

`pagedrop` publishes Markdown, HTML, and agent artifacts to a PageDrop server
from the terminal or from an automation/agent pipeline. It authenticates with a
scoped API token (never your account password).

## Install

From the monorepo:

```bash
cd apps/cli
pnpm install
pnpm build          # compiles to dist/
node dist/index.js --help
```

To use it as a global `pagedrop` command, link it: `pnpm link --global` (or
`npm i -g` once published).

## Authentication

1. In the PageDrop web app, create an API token scoped to the workspace and
   projects the agent should touch. Grant only the scopes it needs:
   - `versions:write` — publish new versions (required for `publish`)
   - `versions:read` / `projects:read` — `versions`, `info`, `pull`
   - `assets:write` — upload images referenced by published content
   - `comments:read` / `comments:write` — `comments list` / `reply`, `resolve`, `reopen`
   - `share_links:create` — `share`
2. Log in with the token; the CLI verifies it against `/auth/whoami` and stores
   it at `~/.pagedrop/config.json` (mode `0600`).

```bash
pagedrop login --token pd_live_xxx --url https://pagedrop.justinhuang.top
```

The token plaintext is shown by the server only once at creation time — store it
securely. The CLI keeps it locally in the config file with owner-only
permissions.

### Environment variables (CI / ephemeral use)

Set these to skip the config file entirely; they override any stored profile:

- `PAGEDROP_TOKEN` — API token
- `PAGEDROP_URL` — server base URL
- `PAGEDROP_WORKSPACE` — default workspace slug
- `PAGEDROP_HOME` — override config directory (default `~/.pagedrop`)
- `PAGEDROP_PROFILE` — select a named profile

## Commands

```bash
# Verify the current credential
pagedrop whoami

# Publish a file (content type inferred: .md → markdown, .html → safe_html)
pagedrop publish notes.md -w my-workspace -s release-notes -m "v1.2 notes"

# Publish from stdin (agents pipe content directly)
generate_report | pagedrop publish - -w my-workspace -s daily-report -T "Daily Report"

# Control content type / visibility
pagedrop publish page.html -w ws -s landing -c safe_html -v public

# List versions of a project (never overwrites; each publish is a new version)
pagedrop versions -w my-workspace -s release-notes

# Show project metadata
pagedrop info -w my-workspace -s release-notes

# Create a share link (optionally password-protected / expiring)
pagedrop share -w my-workspace -s release-notes --password s3cret --expires-at 2026-12-31T00:00:00Z

# Pull a project's content + attached images into a local directory
pagedrop pull -w my-workspace -s release-notes -o ./out

# Read and manage comments (agent-ready with --json)
pagedrop comments list -w my-workspace -s release-notes --status open --json
pagedrop comments reply <comment_id> "Addressed in v3." -w my-workspace -s release-notes
pagedrop comments resolve <comment_id>
pagedrop comments reopen <comment_id>
```

### Images

When publishing a **file** (not stdin), the CLI scans the content for local
image references (Markdown `![](path)` and HTML `<img src>`), uploads each to
`/assets`, and rewrites the reference to a stable `pagedrop://asset/<id>` ref
before publishing. Remote URLs, `data:` URIs, and existing `pagedrop://` refs
are left untouched. Pass `--no-images` to skip this. `pagedrop pull` reverses
the process: it downloads referenced assets into an `assets/` folder and
rewrites refs to local paths.

### Publish options

| Flag | Meaning |
| --- | --- |
| `-w, --workspace <slug>` | Target workspace (required) |
| `-s, --slug <slug>` | Project slug (required) |
| `-T, --title <title>` | Page title (defaults to filename/slug) |
| `-c, --content-type <type>` | `markdown`, `safe_html`, or `sandbox_html` |
| `-v, --visibility <v>` | `public`, `unlisted`, or `private` (default) |
| `-m, --message <msg>` | Changelog message for this version |
| `--summary <text>` | Short summary |
| `--no-images` | Do not upload/rewrite local images referenced in the content |
| `--force` | Publish even if the secret scanner flags content |

## Secret scanning

Publishing runs a server-side secret scan. If secrets are detected the publish
is **blocked** (exit code `2`) and the CLI prints masked previews only — full
secret values are never echoed. Review the findings, remove the secrets, and
re-publish. Use `--force` only if you are certain the matches are false
positives.

## Profiles

`pagedrop login --name <profile>` stores multiple named credentials. Select one
per-command with `--profile <name>` or via `PAGEDROP_PROFILE`. The `default`
profile is used when none is specified.

# PageDrop

A multi-user, versioned Markdown / HTML publishing platform for humans and AI agents.

Publish Markdown or HTML and get a safe, versioned, mobile-friendly URL. Supports
workspaces, per-project visibility (public / unlisted / private), password &
expiring share links, scoped API tokens for agents, secret scanning, and a CLI.

> Target deployment: `https://pagedrop.justinhuang.top`

## For AI agents / CLI (zero-GUI onboarding)

PageDrop is built to be driven by CLI agents. An agent can create the user's
account, mint a scoped API token, and publish — without the user opening the web
app. Machine-readable onboarding lives at
[`/llms.txt`](https://pagedrop.justinhuang.top/llms.txt).

```bash
# Install the CLI (not yet on npm — build from the monorepo):
cd apps/cli && pnpm install && pnpm build && pnpm link --global

# Get a credential (pick one). Each mints + stores a scoped token at ~/.pagedrop/config.json:
pagedrop register --email you@example.com --generate-password   # emailed 6-digit code
pagedrop auth github                                            # GitHub OAuth device flow
pagedrop login --email you@example.com --password ...           # existing account
pagedrop login --token pd_live_xxx                              # pre-provisioned token

# Publish
pagedrop publish report.md -w <workspace> -s <slug> -T "Title"
```

The user can open the printed URL on any device, or sign in later at the base URL
to manage their pages. See [`docs/cli.md`](docs/cli.md) for the full flow.

## Tech stack

| Area | Tech |
| --- | --- |
| Main web app | Vue 3 + Vite + TypeScript + Pinia + Tailwind (`apps/web-vue`) |
| Artifact renderer | React + Vite + TypeScript (`apps/renderer-react`) |
| Backend API | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + PostgreSQL (`backend`) |
| CLI | Node + TypeScript + Commander (`apps/cli`) |
| Infra | Docker Compose + Caddy (`infra`) |

## Monorepo layout

```
pagedrop/
  apps/
    web-vue/        # Vue main product app
    renderer-react/ # React artifact renderer
    cli/            # pagedrop CLI
  backend/          # FastAPI backend
  infra/            # docker-compose, Caddyfile, env example
  docs/             # PRD, handoff, agent skill docs
```

## Quick start (backend)

```bash
cd backend
uv sync
cp ../infra/.env.example .env   # then edit
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# http://localhost:8000/api/health
```

## Development phases

Implemented incrementally per the handoff document. See `docs/` for the full PRD
and phase plan.

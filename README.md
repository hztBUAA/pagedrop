# PageDrop

A multi-user, versioned Markdown / HTML publishing platform for humans and AI agents.

Publish Markdown or HTML and get a safe, versioned, mobile-friendly URL. Supports
workspaces, per-project visibility (public / unlisted / private), password &
expiring share links, scoped API tokens for agents, secret scanning, and a CLI.

> Target deployment: `https://pagedrop.justinhuang.top`

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

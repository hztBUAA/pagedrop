# Deploying PageDrop

The production stack runs three services via Docker Compose:

- **postgres** — PostgreSQL 16 (persistent volume `pg_data`)
- **backend** — FastAPI (gunicorn + uvicorn workers). Runs `alembic upgrade head`
  on every boot, then serves the API on port 8000 (internal only).
- **web** — Caddy. Serves the built Vue SPA at `/`, the React renderer at
  `/render/`, and reverse-proxies `/api/*` to the backend. Provisions HTTPS
  automatically for the configured domain.

```
Internet ──HTTPS──▶ Caddy (web) ──┬── /            → Vue SPA (static)
                                  ├── /render/     → React renderer (static)
                                  └── /api/*        → backend:8000 (FastAPI)
                                                          │
                                                     postgres:5432
```

## Prerequisites

- A host with Docker + Docker Compose v2.
- DNS: point `pagedrop.justinhuang.top` (A/AAAA record) at the host so Caddy can
  obtain a Let's Encrypt certificate. Ports **80** and **443** must be reachable.

## Configure

From `infra/`:

```bash
cp .env.example .env
```

Edit `.env` and set, at minimum:

- `POSTGRES_PASSWORD` — a strong database password
- `JWT_SECRET` — long random string (session cookie signing)
- `TOKEN_PEPPER` — long random string (API/share token hashing)
- `SITE_ADDRESS` — `pagedrop.justinhuang.top` for production HTTPS
- `APP_BASE_URL` / `CORS_ORIGINS` — `https://pagedrop.justinhuang.top`
- `COOKIE_SECURE=true` (HTTPS only)

Generate secrets with e.g. `openssl rand -hex 32`.

`DATABASE_URL` defaults to the bundled Postgres service and only needs changing
if you point at an external database.

## Launch

```bash
cd infra
docker compose up -d --build
```

Caddy will obtain a certificate on first boot (allow a minute). Then visit
`https://pagedrop.justinhuang.top`.

Check status and logs:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f web
```

## Local smoke test (plain HTTP, no domain)

To exercise the whole stack without TLS/DNS, run it on a local port:

```bash
# .env: SITE_ADDRESS=:80, COOKIE_SECURE=false, APP_BASE_URL=http://localhost:8080
docker compose -f docker-compose.yml \
  -p pdlocal up -d --build
# map the web container's :80 to a host port via an override, or publish 8080:80
curl http://localhost/api/health
```

## Operations

- **Migrations** run automatically on backend start. To run manually:
  `docker compose exec backend alembic upgrade head`.
- **Database backup:** `docker compose exec postgres pg_dump -U pagedrop pagedrop > backup.sql`.
- **Update:** pull new code, then `docker compose up -d --build`. The backend
  applies any new migrations on restart; published versions are immutable and
  never modified by deploys.
- **Data persistence:** Postgres data lives in the `pg_data` volume and Caddy's
  certificates in `caddy_data`. `docker compose down` keeps volumes; add `-v`
  only when you intend to wipe all data.

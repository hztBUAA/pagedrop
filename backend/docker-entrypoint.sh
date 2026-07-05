#!/usr/bin/env bash
# Run database migrations before starting the app server. Safe to run on every
# boot: alembic applies only pending migrations.
set -euo pipefail

echo "[entrypoint] running database migrations..."
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"

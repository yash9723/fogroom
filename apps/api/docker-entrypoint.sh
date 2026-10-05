#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running database migrations..."
  python -m alembic upgrade head
fi

if [ "${RUN_SEED:-false}" = "true" ]; then
  echo "Seeding demo data..."
  python -m app.seed
fi

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers

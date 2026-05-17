#!/usr/bin/env bash
set -e

echo "Waiting for Postgres..."
python - <<'PY'
import os, time, sys
import psycopg2
url = os.environ.get("DATABASE_URL", "")
dsn = url.replace("postgresql+asyncpg", "postgresql").replace("+psycopg2", "")
if not dsn.startswith("postgresql"):
    sys.exit(0)  # sqlite local — nothing to wait for
for _ in range(40):
    try:
        psycopg2.connect(dsn).close()
        print("Postgres up.")
        break
    except Exception as e:
        print("...", e); time.sleep(1.5)
else:
    sys.exit("Postgres never came up")
PY

# Postgres uses Alembic migrations; SQLite auto-creates on startup.
if [[ "${DATABASE_URL}" == postgresql* ]]; then
  echo "Running Alembic migrations..."
  alembic upgrade head
fi

echo "Seeding demo data (idempotent)..."
python -m scripts.seed || true

# Railway/most PaaS inject $PORT and route to it; fall back to 8000 locally.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

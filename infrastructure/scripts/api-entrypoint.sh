#!/usr/bin/env bash
# =============================================================================
# API Entrypoint — runs Alembic migrations then starts uvicorn
# =============================================================================
set -euo pipefail

echo "[API] Running database migrations..."
alembic upgrade head || {
    echo "[API] Migration failed — starting anyway (DB may need manual fix)"
}

echo "[API] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"

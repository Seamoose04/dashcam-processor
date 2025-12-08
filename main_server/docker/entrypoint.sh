#!/usr/bin/env bash
set -euo pipefail

cd /app

export MAIN_SERVER_DATABASE_URL="${MAIN_SERVER_DATABASE_URL:-sqlite:////data/dev.db}"
export MAIN_SERVER_HOST="${MAIN_SERVER_HOST:-0.0.0.0}"
export MAIN_SERVER_PORT="${MAIN_SERVER_PORT:-8080}"

alembic -c alembic.ini upgrade head

exec uvicorn src.app:app --host "${MAIN_SERVER_HOST}" --port "${MAIN_SERVER_PORT}"

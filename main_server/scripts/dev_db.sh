#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

db_path="dev.db"

if [ -f "$db_path" ]; then
  echo "[dev-db] $db_path already exists"
  exit 0
fi

export MAIN_SERVER_DATABASE_URL="${MAIN_SERVER_DATABASE_URL:-sqlite:///./${db_path}}"
alembic -c alembic.ini upgrade head
echo "[dev-db] created $db_path via Alembic"

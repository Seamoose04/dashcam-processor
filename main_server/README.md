# Main Server

Authoritative task coordinator and metadata store for the dashcam pipeline. Provides a minimal API that devices use to pull tasks, mark them complete, and publish new tasks. Uses a simple two-state task model (`pending`, `complete`) and a pull-based workflow.

## Quickstart (dev)

Requirements: Python 3.11+, `uvicorn`, `fastapi`, `sqlalchemy`, `alembic`, `pydantic`.

```bash
pip install -r requirements.txt
./scripts/dev_db.sh   # runs Alembic migrations to create dev.db
uvicorn src.app:app --reload --port 8080
```

### Database migrations (Alembic)
- Config lives in `alembic.ini` with scripts under `alembic/`.
- Local DB URL defaults to `sqlite:///./dev.db` (override with `MAIN_SERVER_DATABASE_URL`).
- Apply migrations manually with `alembic upgrade head` or via `scripts/dev_db.sh`.

## Key Responsibilities
- Hold the task database (source of truth)
- Expose HTTP API for devices to pull and complete tasks
- Create tasks triggered by ingestion events
- Persist finalized metadata for the WebUI

## Layout
- `alembic/` — Alembic environment and versioned migrations
- `config/` — defaults and logging config
- `db/` — legacy schema reference
- `src/` — application code (API, services, repositories)
- `scripts/` — helper scripts (dev db, seeding)
- `docker/` — container assets
- `tests/` — unit/integration tests

## Minimal API Surface
- `POST /healthz`
- `POST /tasks/pull`
- `POST /tasks/complete`
- `POST /ingestion`

## Next Steps
- Add device-specific task validation rules
- Implement auth for non-LAN deployments

-- Minimal schema for the two-state task model

CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trip_date TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    device_class TEXT NOT NULL,
    video_id TEXT,
    state TEXT NOT NULL CHECK (state IN ('pending','complete')),
    inputs TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY(video_id) REFERENCES videos(video_id)
);

CREATE TABLE IF NOT EXISTS ingestion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    device TEXT,
    path TEXT,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(video_id) REFERENCES videos(video_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_state_device_created ON tasks(state, device_class, created_at);

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy import text

from src.core.models import Task


class BaseRepo:
    def __init__(self, session):
        self.session = session


class TaskRepo(BaseRepo):
    def pull_oldest_pending(self, device_class: str) -> Optional[Task]:
        sql = text(
            """
            SELECT task_id, task_type, device_class, video_id, state, inputs
            FROM tasks
            WHERE state = 'pending' AND device_class = :device_class
            ORDER BY created_at ASC
            LIMIT 1
            """
        )
        row = self.session.execute(sql, {"device_class": device_class}).mappings().first()
        if not row:
            return None
        inputs = json.loads(row["inputs"]) if row["inputs"] else {}
        return Task(
            task_id=row["task_id"],
            task_type=row["task_type"],
            device_class=row["device_class"],
            video_id=row["video_id"],
            state=row["state"],
            inputs=inputs,
        )

    def mark_complete(self, task_id: str) -> None:
        sql = text("UPDATE tasks SET state='complete', completed_at=CURRENT_TIMESTAMP WHERE task_id=:task_id")
        self.session.execute(sql, {"task_id": task_id})

    def create_task(self, task_id: str, task_type: str, device_class: str, video_id: Optional[str], inputs: Dict[str, Any]) -> None:
        sql = text(
            """
            INSERT INTO tasks (task_id, task_type, device_class, video_id, state, inputs)
            VALUES (:task_id, :task_type, :device_class, :video_id, 'pending', :inputs)
            """
        )
        self.session.execute(
            sql,
            {
                "task_id": task_id,
                "task_type": task_type,
                "device_class": device_class,
                "video_id": video_id,
                "inputs": json.dumps(inputs),
            },
        )


class VideoRepo(BaseRepo):
    def get(self, video_id: str):
        sql = text("SELECT video_id FROM videos WHERE video_id = :video_id")
        return self.session.execute(sql, {"video_id": video_id}).first()

    def create(self, video_id: str, trip_date: Optional[str] = None):
        sql = text("INSERT INTO videos (video_id, trip_date, status) VALUES (:video_id, :trip_date, 'ingested')")
        self.session.execute(sql, {"video_id": video_id, "trip_date": trip_date})


class IngestionRepo(BaseRepo):
    def record(self, video_id: str, device: str, path: str) -> None:
        sql = text("INSERT INTO ingestion_events (video_id, device, path) VALUES (:video_id, :device, :path)")
        self.session.execute(sql, {"video_id": video_id, "device": device, "path": path})

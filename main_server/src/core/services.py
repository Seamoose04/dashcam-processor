from __future__ import annotations

import uuid
from typing import Iterable, Optional

from src.core.models import Task, TaskSpawn
from src.db.repos import TaskRepo, VideoRepo, IngestionRepo


class TaskService:
    def __init__(self, session):
        self.tasks = TaskRepo(session)
        self.videos = VideoRepo(session)
        self.ingestions = IngestionRepo(session)

    def pull_task(self, device_class: str) -> Optional[Task]:
        return self.tasks.pull_oldest_pending(device_class=device_class)

    def complete_task(self, task_id: str, spawn: Iterable[TaskSpawn]) -> None:
        self.tasks.mark_complete(task_id)
        for spawn_task in spawn:
            self.tasks.create_task(
                task_id=str(uuid.uuid4()),
                task_type=spawn_task.task_type,
                device_class=spawn_task.device_class,
                video_id=spawn_task.video_id,
                inputs=spawn_task.inputs,
            )

    def create_ingestion_task(self, video_id: str, device: str, path: str) -> None:
        if not self.videos.get(video_id):
            self.videos.create(video_id=video_id)
        self.ingestions.record(video_id=video_id, device=device, path=path)
        self.tasks.create_task(
            task_id=str(uuid.uuid4()),
            task_type="ingestion",
            device_class="server",
            video_id=video_id,
            inputs={"device": device, "path": path},
        )

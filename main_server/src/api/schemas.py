from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from src.core.models import Task, TaskSpawn


class TaskPullRequest(BaseModel):
    device_class: str = Field(..., description="Device class requesting work (e.g., jetson, gpu4090, shed_nas, server)")


class TaskPullResponse(BaseModel):
    task_id: str
    task_type: str
    device_class: str
    video_id: Optional[str]
    inputs: dict

    @classmethod
    def from_model(cls, task: Task) -> "TaskPullResponse":
        return cls(
            task_id=task.task_id,
            task_type=task.task_type,
            device_class=task.device_class,
            video_id=task.video_id,
            inputs=task.inputs,
        )


class SpawnTask(BaseModel):
    task_type: str
    device_class: str
    video_id: Optional[str]
    inputs: dict = Field(default_factory=dict)

    def to_task_spawn(self) -> TaskSpawn:
        return TaskSpawn(
            task_type=self.task_type,
            device_class=self.device_class,
            video_id=self.video_id,
            inputs=self.inputs,
        )


class TaskCompleteRequest(BaseModel):
    task_id: str
    spawn: List[SpawnTask] = Field(default_factory=list)


class IngestionRequest(BaseModel):
    video_id: str
    device: str
    path: str

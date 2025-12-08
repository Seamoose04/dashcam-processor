from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Task:
    task_id: str
    task_type: str
    device_class: str
    video_id: Optional[str]
    state: str
    inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskSpawn:
    task_type: str
    device_class: str
    video_id: Optional[str]
    inputs: Dict[str, Any] = field(default_factory=dict)

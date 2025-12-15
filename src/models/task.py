"""SQLAlchemy models for the task management system."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class InputOutput(Base):
    """Input/Output file references for tasks."""

    __tablename__ = "input_output"

    id = Column(Integer, primary_key=True)
    device = Column(String(128), nullable=False)
    path = Column(String(512), nullable=False)
    type = Column(String(64), nullable=False)
    temporary = Column(Boolean, default=False)

    # Relationship back to task
    task_id = Column(Integer, ForeignKey("tasks.task_id"))
    task = relationship("Task", back_populates="inputs_outputs")

class Task(Base):
    """Main task entity representing work to be done in the pipeline."""

    __tablename__ = "tasks"

    task_id = Column(Integer, primary_key=True)
    task_type = Column(String(64), nullable=False, index=True)
    state = Column(
        String(32),
        nullable=False,
        default="pending",
        index=True
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    video_id = Column(String(128), index=True)

    # JSON fields for flexible metadata
    inputs = Column(JSON, default=list)  # List of input references
    outputs = Column(JSON, default=list)  # List of output references
    metadata = Column(JSON, default=dict)  # Task-specific metadata
    device_capabilities_required = Column(JSON, default=dict)

    # Relationships for input/output objects (denormalized in JSON + normalized for queries)
    inputs_outputs = relationship("InputOutput", back_populates="task")

    def to_dict(self) -> dict:
        """Convert task to dictionary representation."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "state": self.state,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "video_id": self.video_id,
            "inputs": self.inputs or [],
            "outputs": self.outputs or [],
            "metadata": self.metadata or {},
            "device_capabilities_required": self.device_capabilities_required or {},
        }

# Create indexes for common query patterns
Index("idx_tasks_state_type", Task.task_type, Task.state)
Index("idx_tasks_video_id", Task.video_id)
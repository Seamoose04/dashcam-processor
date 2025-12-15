"""SQLAlchemy models for device registry."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Device(Base):
    """Device entity representing workers in the pipeline."""

    __tablename__ = "devices"

    device_id = Column(Integer, primary_key=True)
    hostname = Column(String(128), unique=True, nullable=False)
    device_type = Column(
        String(64),
        nullable=False,
        index=True
    )
    status = Column(
        String(32),
        nullable=False,
        default="offline",
        index=True
    )
    last_heartbeat = Column(DateTime)
    tasks_running = Column(Integer, default=0)
    capabilities = Column(JSON, default=dict)

    def to_dict(self) -> dict:
        """Convert device to dictionary representation."""
        return {
            "device_id": self.device_id,
            "hostname": self.hostname,
            "device_type": self.device_type,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "tasks_running": self.tasks_running,
            "capabilities": self.capabilities or {},
        }

# Create indexes for common query patterns
Index("idx_devices_status", Device.status)
Index("idx_devices_type", Device.device_type)
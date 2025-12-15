"""Unit tests for SQLAlchemy models."""
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.task import Task, InputOutput, Base
from src.models.device import Device as DeviceModel

# Use in-memory SQLite database for testing
engine = create_engine('sqlite:///:memory:')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def db_session():
    """Create a database session for testing."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

class TestTaskModel:
    """Test cases for Task model."""

    def test_task_creation(self, db_session):
        """Test creating a task with all required fields."""
        task = Task(
            task_type="INGEST_VIDEO",
            state="pending",
            video_id="video_123"
        )
        db_session.add(task)
        db_session.commit()

        assert task.task_id == 1
        assert task.task_type == "INGEST_VIDEO"
        assert task.state == "pending"
        assert isinstance(task.created_at, datetime)
        assert task.video_id == "video_123"

    def test_task_default_values(self, db_session):
        """Test that default values are set correctly."""
        task = Task(
            task_type="PREPROCESS_VIDEO",
            state="complete"
        )
        db_session.add(task)
        db_session.commit()

        assert task.inputs == []
        assert task.outputs == []
        assert task.metadata == {}
        assert task.device_capabilities_required == {}

    def test_task_to_dict(self, db_session):
        """Test the to_dict method."""
        created_at = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        completed_at = datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

        task = Task(
            task_id=42,
            task_type="HEAVY_PROCESS_VIDEO",
            state="complete",
            created_at=created_at,
            completed_at=completed_at,
            video_id="test_video",
            inputs=["input1.mp4"],
            outputs=["output1.avi"],
            metadata={"key": "value"},
            device_capabilities_required={"gpu": True}
        )

        result = task.to_dict()

        assert result["task_id"] == 42
        assert result["task_type"] == "HEAVY_PROCESS_VIDEO"
        assert result["state"] == "complete"
        assert result["created_at"] == created_at.isoformat()
        assert result["completed_at"] == completed_at.isoformat()
        assert result["video_id"] == "test_video"
        assert result["inputs"] == ["input1.mp4"]
        assert result["outputs"] == ["output1.avi"]
        assert result["metadata"] == {"key": "value"}
        assert result["device_capabilities_required"] == {"gpu": True}

    def test_task_with_none_values(self, db_session):
        """Test handling of None values in to_dict."""
        task = Task(
            task_type="ARCHIVE_VIDEO",
            state="pending"
        )
        db_session.add(task)
        db_session.commit()

        result = task.to_dict()

        assert result["created_at"] is not None
        assert result["completed_at"] is None
        assert result["video_id"] is None

class TestInputOutputModel:
    """Test cases for InputOutput model."""

    def test_input_output_creation(self, db_session):
        """Test creating an input/output reference."""
        io_ref = InputOutput(
            device="indoor-nas-1",
            path="/videos/raw/video.mp4",
            type="input"
        )
        db_session.add(io_ref)
        db_session.commit()

        assert io_ref.id == 1
        assert io_ref.device == "indoor-nas-1"
        assert io_ref.path == "/videos/raw/video.mp4"
        assert io_ref.type == "input"
        assert io_ref.temporary is False

    def test_input_output_temporary_flag(self, db_session):
        """Test the temporary flag."""
        temp_io = InputOutput(
            device="jetson-coral-1",
            path="/tmp/processing/output.avi",
            type="output",
            temporary=True
        )
        db_session.add(temp_io)
        db_session.commit()

        assert temp_io.temporary is True

class TestDeviceModel:
    """Test cases for Device model."""

    def test_device_creation(self, db_session):
        """Test creating a device."""
        device = DeviceModel(
            hostname="jetson-coral-1",
            device_type="jetson_coral",
            status="online",
            tasks_running=2,
            capabilities={"gpu": "NVIDIA Jetson", "memory_gb": 4}
        )
        db_session.add(device)
        db_session.commit()

        assert device.device_id == 1
        assert device.hostname == "jetson-coral-1"
        assert device.device_type == "jetson_coral"
        assert device.status == "online"
        assert device.tasks_running == 2
        assert device.capabilities["gpu"] == "NVIDIA Jetson"

    def test_device_default_values(self, db_session):
        """Test default values for device."""
        device = DeviceModel(
            hostname="rtx-4090-1",
            device_type="rtx_4090"
        )
        db_session.add(device)
        db_session.commit()

        assert device.status == "offline"
        assert device.tasks_running == 0
        assert device.capabilities == {}

    def test_device_to_dict(self, db_session):
        """Test the to_dict method."""
        heartbeat = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        device = DeviceModel(
            device_id=5,
            hostname="shed-nas-1",
            device_type="shed_nas",
            status="online",
            last_heartbeat=heartbeat,
            tasks_running=1,
            capabilities={"storage_tb": 16, "backup_enabled": True}
        )

        result = device.to_dict()

        assert result["device_id"] == 5
        assert result["hostname"] == "shed-nas-1"
        assert result["device_type"] == "shed_nas"
        assert result["status"] == "online"
        assert result["last_heartbeat"] == heartbeat.isoformat()
        assert result["tasks_running"] == 1
        assert result["capabilities"]["storage_tb"] == 16

    def test_device_without_heartbeat(self, db_session):
        """Test device without last_heartbeat set."""
        device = DeviceModel(
            hostname="indoor-nas-1",
            device_type="indoor_nas"
        )
        db_session.add(device)
        db_session.commit()

        result = device.to_dict()

        assert result["last_heartbeat"] is None
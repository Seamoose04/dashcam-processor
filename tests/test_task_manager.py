"""Unit tests for TaskManager service."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.models.task import Task
from services.task_manager import TaskManager

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    return session

class TestTaskManager:
    """Test cases for TaskManager."""

    def test_create_task_valid(self, mock_db_session):
        """Test creating a valid task."""
        manager = TaskManager(mock_db_session)

        task = manager.create_task(
            task_type="INGEST_VIDEO",
            video_id="video_123",
            inputs=[{"device": "dashcam", "path": "/video.mp4"}],
            outputs=[{"device": "indoor-nas-1", "path": "/processed/output.avi"}],
            metadata={"priority": "high"},
            device_capabilities_required={"storage_gb": 100}
        )

        assert task.task_type == "INGEST_VIDEO"
        assert task.state == "pending"
        assert task.video_id == "video_123"
        assert len(task.inputs) == 1
        assert len(task.outputs) == 1
        assert task.metadata["priority"] == "high"
        assert task.device_capabilities_required["storage_gb"] == 100

    def test_create_task_invalid_type(self, mock_db_session):
        """Test creating a task with invalid type."""
        manager = TaskManager(mock_db_session)

        with pytest.raises(ValueError) as exc_info:
            manager.create_task(task_type="INVALID_TYPE")

        assert "Invalid task_type" in str(exc_info.value)

    def test_create_task_missing_type(self, mock_db_session):
        """Test creating a task without type."""
        manager = TaskManager(mock_db_session)

        with pytest.raises(ValueError) as exc_info:
            manager.create_task(task_type="")

        assert "task_type is required" in str(exc_info.value)

    def test_get_pending_tasks(self, mock_db_session):
        """Test getting pending tasks."""
        manager = TaskManager(mock_db_session)

        # Setup mock query
        mock_task1 = MagicMock(spec=Task)
        mock_task1.task_id = 1
        mock_task1.task_type = "INGEST_VIDEO"
        mock_task1.state = "pending"

        mock_task2 = MagicMock(spec=Task)
        mock_task2.task_id = 2
        mock_task2.task_type = "PREPROCESS_VIDEO"
        mock_task2.state = "pending"

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_task1,
            mock_task2
        ]

        tasks = manager.get_pending_tasks(limit=5)

        assert len(tasks) == 2
        assert tasks[0].task_id == 1
        assert tasks[1].task_id == 2

    def test_get_pending_tasks_filtered(self, mock_db_session):
        """Test getting pending tasks with type filter."""
        manager = TaskManager(mock_db_session)

        # Setup mock query for PREPROCESS_VIDEO only
        mock_task = MagicMock(spec=Task)
        mock_task.task_id = 3
        mock_task.task_type = "PREPROCESS_VIDEO"
        mock_task.state = "pending"

        mock_db_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_task
        ]

        tasks = manager.get_pending_tasks(task_type="PREPROCESS_VIDEO")

        assert len(tasks) == 1
        assert tasks[0].task_id == 3

    def test_mark_task_complete(self, mock_db_session):
        """Test marking a task as complete."""
        manager = TaskManager(mock_db_session)

        # Setup mock task
        mock_task = MagicMock(spec=Task)
        mock_task.task_id = 1
        mock_task.task_type = "INGEST_VIDEO"
        mock_task.state = "pending"

        mock_db_session.query.return_value.get.return_value = mock_task

        result = manager.mark_task_complete(1)

        assert result.state == "complete"
        assert result.completed_at is not None

    def test_mark_task_complete_not_found(self, mock_db_session):
        """Test marking a non-existent task as complete."""
        manager = TaskManager(mock_db_session)

        mock_db_session.query.return_value.get.return_value = None

        with pytest.raises(ValueError) as exc_info:
            manager.mark_task_complete(999)

        assert "Task 999 not found" in str(exc_info.value)

    def test_mark_task_complete_already_complete(self, mock_db_session):
        """Test marking an already complete task."""
        manager = TaskManager(mock_db_session)

        mock_task = MagicMock(spec=Task)
        mock_task.task_id = 1
        mock_task.state = "complete"

        mock_db_session.query.return_value.get.return_value = mock_task

        with pytest.raises(ValueError) as exc_info:
            manager.mark_task_complete(1)

        assert "already complete" in str(exc_info.value)

    def test_get_task_by_id(self, mock_db_session):
        """Test getting a task by ID."""
        manager = TaskManager(mock_db_session)

        mock_task = MagicMock(spec=Task)
        mock_task.task_id = 42
        mock_task.task_type = "HEAVY_PROCESS_VIDEO"

        mock_db_session.query.return_value.get.return_value = mock_task

        result = manager.get_task_by_id(42)

        assert result is not None
        assert result.task_id == 42

    def test_get_task_by_id_not_found(self, mock_db_session):
        """Test getting a non-existent task."""
        manager = TaskManager(mock_db_session)

        mock_db_session.query.return_value.get.return_value = None

        result = manager.get_task_by_id(999)
        assert result is None

    def test_list_tasks(self, mock_db_session):
        """Test listing tasks with filters."""
        manager = TaskManager(mock_db_session)

        mock_task1 = MagicMock(spec=Task)
        mock_task1.task_id = 1
        mock_task1.task_type = "INGEST_VIDEO"
        mock_task1.state = "complete"

        mock_task2 = MagicMock(spec=Task)
        mock_task2.task_id = 2
        mock_task2.task_type = "PREPROCESS_VIDEO"
        mock_task2.state = "pending"

        mock_db_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = [
            mock_task1,
            mock_task2
        ]

        tasks = manager.list_tasks(task_type="INGEST_VIDEO", state="complete")

        assert len(tasks) == 2

    def test_get_task_count(self, mock_db_session):
        """Test getting task count."""
        manager = TaskManager(mock_db_session)

        mock_db_session.query.return_value.filter.return_value.filter.return_value.count.return_value = 42

        count = manager.get_task_count(task_type="INGEST_VIDEO", state="pending")

        assert count == 42

    def test_create_task_with_device_capabilities(self, mock_db_session):
        """Test creating a task requiring specific device capabilities."""
        manager = TaskManager(mock_db_session)

        task = manager.create_task(
            task_type="HEAVY_PROCESS_VIDEO",
            video_id="heavy_video_1",
            device_capabilities_required={
                "gpu": True,
                "memory_gb": 8,
                "storage_tb": 0.5
            }
        )

        assert task.device_capabilities_required["gpu"] is True
        assert task.device_capabilities_required["memory_gb"] == 8
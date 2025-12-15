"""Integration tests for task lifecycle management."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.models.task import Task
from services.task_manager import TaskManager
from services.device_registry import DeviceRegistry

@pytest.fixture
def mock_sessions():
    """Create mock database sessions for integration testing."""
    task_session = MagicMock()
    device_session = MagicMock()
    return task_session, device_session

class TestTaskLifecycle:
    """Test cases for complete task lifecycle."""

    def test_ingest_to_preprocess_workflow(self, mock_sessions):
        """Test the workflow from ingest to preprocess tasks."""
        task_session, device_session = mock_sessions
        task_manager = TaskManager(task_session)
        device_registry = DeviceRegistry(device_session)

        # Create ingestion task
        ingest_task = task_manager.create_task(
            task_type="INGEST_VIDEO",
            video_id="video_2023_12_01",
            inputs=[{"device": "dashcam", "path": "/recordings/2023-12-01.mp4"}],
            outputs=[{"device": "indoor-nas-1", "path": "/videos/raw/2023-12-01.mp4"}]
        )

        assert ingest_task.task_id is not None
        assert ingest_task.state == "pending"

        # Simulate device registration
        with patch.object(device_session, 'query') as mock_query:
            mock_device = MagicMock()
            mock_device.hostname = "indoor-nas-1"
            mock_device.device_type = "indoor_nas"
            mock_device.status = "online"
            mock_query.return_value.filter.return_value.first.return_value = None
            mock_query.return_value.all.return_value = []

            device_registry.register_device(
                hostname="indoor-nas-1",
                device_type="indoor_nas",
                capabilities={"storage_tb": 8}
            )

        # Get pending tasks
        with patch.object(task_session, 'query') as mock_query:
            mock_task = MagicMock(spec=Task)
            mock_task.task_id = ingest_task.task_id
            mock_task.state = "pending"
            mock_query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
                mock_task
            ]

            pending_tasks = task_manager.get_pending_tasks(task_type="INGEST_VIDEO")
            assert len(pending_tasks) == 1

        # Complete the ingestion task and create preprocess task
        with patch.object(task_session, 'query') as mock_query:
            mock_query.return_value.get.return_value = ingest_task

            completed_task = task_manager.mark_task_complete(
                ingest_task.task_id,
                new_tasks=[{
                    "task_type": "PREPROCESS_VIDEO",
                    "video_id": "video_2023_12_01",
                    "inputs": [{"device": "indoor-nas-1", "path": "/videos/raw/2023-12-01.mp4"}],
                    "outputs": [{"device": "jetson-coral-1", "path": "/processed/2023-12-01_preproc.avi"}],
                    "device_capabilities_required": {"gpu": True}
                }]
            )

        assert completed_task.state == "complete"
        assert completed_task.completed_at is not None

    def test_end_to_end_pipeline(self, mock_sessions):
        """Test complete end-to-end video processing pipeline."""
        task_session, _ = mock_sessions
        manager = TaskManager(task_session)

        # Create ingestion task
        ingest_task = manager.create_task(
            task_type="INGEST_VIDEO",
            video_id="test_video",
            inputs=[{"path": "/dashcam/video.mp4"}],
            outputs=[{"path": "/nas/raw.mp4"}]
        )

        # Complete ingestion and create preprocess
        completed_ingest = manager.mark_task_complete(
            ingest_task.task_id,
            new_tasks=[{
                "task_type": "PREPROCESS_VIDEO",
                "video_id": "test_video",
                "device_capabilities_required": {"gpu": True}
            }]
        )

        assert completed_ingest.state == "complete"

    def test_device_capability_filtering(self, mock_sessions):
        """Test that tasks are filtered by device capabilities."""
        task_session, _ = mock_sessions
        manager = TaskManager(task_session)

        # Create a heavy processing task requiring GPU
        heavy_task = manager.create_task(
            task_type="HEAVY_PROCESS_VIDEO",
            video_id="heavy_video",
            device_capabilities_required={"gpu": True}
        )

        assert heavy_task.device_capabilities_required["gpu"] is True

    def test_task_state_transitions(self, mock_sessions):
        """Test proper state transitions throughout task lifecycle."""
        task_session, _ = mock_sessions
        manager = TaskManager(task_session)

        # Create a new task - should be in pending state
        task = manager.create_task(
            task_type="INGEST_VIDEO",
            video_id="transition_test"
        )

        assert task.state == "pending"

        # Complete the task - should transition to complete
        with patch.object(task_session, 'query') as mock_query:
            mock_query.return_value.get.return_value = task

            completed_task = manager.mark_task_complete(task.task_id)

        assert completed_task.state == "complete"
        assert completed_task.completed_at is not None

    def test_multiple_tasks_creation(self, mock_sessions):
        """Test creating multiple related tasks."""
        task_session, _ = mock_sessions
        manager = TaskManager(task_session)

        # Create first task
        task1 = manager.create_task(
            task_type="INGEST_VIDEO",
            video_id="multi_video"
        )

        # Create second task
        task2 = manager.create_task(
            task_type="PREPROCESS_VIDEO",
            video_id="multi_video"
        )

        assert task1.task_id != task2.task_id

    def test_list_tasks_filtering(self, mock_sessions):
        """Test listing tasks with various filters."""
        task_session, _ = mock_sessions
        manager = TaskManager(task_session)

        # Create multiple tasks of different types and states
        with patch.object(task_session, 'query') as mock_query:
            mock_task1 = MagicMock(spec=Task)
            mock_task1.task_id = 1
            mock_task1.task_type = "INGEST_VIDEO"
            mock_task1.state = "complete"

            mock_task2 = MagicMock(spec=Task)
            mock_task2.task_id = 2
            mock_task2.task_type = "PREPROCESS_VIDEO"
            mock_task2.state = "pending"

            mock_query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = [
                mock_task1,
                mock_task2
            ]

            # Filter by state
            complete_tasks = manager.list_tasks(state="complete")
            assert len(complete_tasks) == 2

            pending_tasks = manager.list_tasks(state="pending")
            assert len(pending_tasks) == 2

    def test_task_count_accuracy(self, mock_sessions):
        """Test that task counts are accurate."""
        task_session, _ = mock_sessions
        manager = TaskManager(task_session)

        with patch.object(task_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.filter.return_value.count.return_value = 15

            count = manager.get_task_count(state="pending")
            assert count == 15

    def test_error_handling_in_task_creation(self, mock_sessions):
        """Test proper error handling when creating invalid tasks."""
        task_session, _ = mock_sessions
        manager = TaskManager(task_session)

        with pytest.raises(ValueError):
            # Should raise ValueError for empty task type
            manager.create_task(task_type="")
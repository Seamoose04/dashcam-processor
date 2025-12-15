"""Integration tests for device adapters."""
import pytest
from unittest.mock import MagicMock, patch

from services.device_registry import DeviceRegistry
from services.task_manager import TaskManager

@pytest.fixture
def mock_sessions():
    """Create mock database sessions for integration testing."""
    task_session = MagicMock()
    device_session = MagicMock()
    return task_session, device_session

class TestDeviceAdapters:
    """Test cases for device adapter integrations."""

    def test_device_registration_with_capabilities(self, mock_sessions):
        """Test registering devices with specific capabilities."""
        _, device_session = mock_sessions
        registry = DeviceRegistry(device_session)

        # Register Jetson Coral device
        jetson_device = registry.register_device(
            hostname="jetson-coral-1",
            device_type="jetson_coral",
            capabilities={
                "gpu": "NVIDIA Jetson Nano",
                "memory_gb": 4,
                "storage_tb": 0.5
            }
        )

        assert jetson_device.hostname == "jetson-coral-1"
        assert jetson_device.capabilities["memory_gb"] == 4

    def test_multiple_devices_of_same_type(self, mock_sessions):
        """Test registering multiple devices of the same type."""
        _, device_session = mock_sessions
        registry = DeviceRegistry(device_session)

        # Clear mock to avoid conflicts
        device1 = MagicMock()
        device2 = MagicMock()

        with patch.object(device_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.side_effect = [
                None,  # First call - no existing device
                device1,  # Second call - device exists
                device2   # Third call - second device exists
            ]

            # Register first RTX 4090
            rtx1 = registry.register_device(
                hostname="rtx-4090-1",
                device_type="rtx_4090",
                capabilities={"gpu": "RTX 4090", "memory_gb": 24}
            )

            # Register second RTX 4090
            rtx2 = registry.register_device(
                hostname="rtx-4090-2",
                device_type="rtx_4090",
                capabilities={"gpu": "RTX 4090", "memory_gb": 24}
            )

        assert rtx1.hostname == "rtx-4090-1"
        assert rtx2.hostname == "rtx-4090-2"

    def test_device_online_offline_transitions(self, mock_sessions):
        """Test device status transitions."""
        _, device_session = mock_sessions
        registry = DeviceRegistry(device_session)

        # Setup mock device
        device = MagicMock()
        device.hostname = "indoor-nas-1"
        device.status = "online"

        with patch.object(device_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = device

            # Update heartbeat - should keep online status
            result = registry.update_heartbeat("indoor-nas-1")
            assert result is True
            assert device.status == "online"

            # Mark offline
            result = registry.mark_device_offline("indoor-nas-1")
            assert result is True
            assert device.status == "offline"

    def test_task_assignment_to_capable_devices(self, mock_sessions):
        """Test that tasks are assigned to devices with matching capabilities."""
        task_session, _ = mock_sessions
        manager = TaskManager(task_session)

        # Create a GPU-intensive task
        gpu_task = manager.create_task(
            task_type="HEAVY_PROCESS_VIDEO",
            video_id="gpu_intensive_video",
            device_capabilities_required={"gpu": True}
        )

        assert gpu_task.device_capabilities_required["gpu"] is True

    def test_device_heartbeat_timeout(self, mock_sessions):
        """Test that devices are marked offline after heartbeat timeout."""
        _, device_session = mock_sessions
        registry = DeviceRegistry(device_session)

        # Setup mock devices with different heartbeat times
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        recent_heartbeat = now - timedelta(minutes=1)
        old_heartbeat = now - timedelta(minutes=10)

        device_recent = MagicMock()
        device_recent.hostname = "recent-device"
        device_recent.status = "online"
        device_recent.last_heartbeat = recent_heartbeat

        device_old = MagicMock()
        device_old.hostname = "old-device"
        device_old.status = "online"
        device_old.last_heartbeat = old_heartbeat

        with patch.object(device_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = [
                device_recent,
                device_old
            ]

            online_devices = registry.get_online_devices()

            # Only the recent device should be considered online
            assert len(online_devices) == 1
            assert online_devices[0].hostname == "recent-device"

    def test_device_type_filtering(self, mock_sessions):
        """Test filtering devices by type."""
        _, device_session = mock_sessions
        registry = DeviceRegistry(device_session)

        # Setup mock devices of different types
        jetson_device = MagicMock()
        jetson_device.hostname = "jetson-coral-1"
        jetson_device.device_type = "jetson_coral"

        rtx_device = MagicMock()
        rtx_device.hostname = "rtx-4090-1"
        rtx_device.device_type = "rtx_4090"

        nas_device = MagicMock()
        nas_device.hostname = "indoor-nas-1"
        nas_device.device_type = "indoor_nas"

        with patch.object(device_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = [
                jetson_device,
                rtx_device
            ]

            # Get only Jetson Coral devices
            jetson_devices = registry.get_devices_by_type("jetson_coral")
            assert len(jetson_devices) == 1
            assert jetson_devices[0].hostname == "jetson-coral-1"

    def test_task_type_to_device_mapping(self, mock_sessions):
        """Test the mapping between task types and device types."""
        _, device_session = mock_sessions
        registry = DeviceRegistry(device_session)

        # Setup mock devices
        jetson_device = MagicMock()
        jetson_device.hostname = "jetson-coral-1"
        jetson_device.device_type = "jetson_coral"
        jetson_device.status = "online"

        rtx_device = MagicMock()
        rtx_device.hostname = "rtx-4090-1"
        rtx_device.device_type = "rtx_4090"
        rtx_device.status = "online"

        with patch.object(device_session, 'query') as mock_query:
            # Test PREPROCESS_VIDEO tasks (should map to jetson_coral)
            mock_query.return_value.filter.return_value.all.return_value = [jetson_device]
            preproc_devices = registry.get_devices_for_task_type("PREPROCESS_VIDEO")
            assert len(preproc_devices) == 1
            assert preproc_devices[0].hostname == "jetson-coral-1"

            # Test HEAVY_PROCESS_VIDEO tasks (should map to rtx_4090)
            mock_query.return_value.filter.return_value.all.return_value = [rtx_device]
            heavy_devices = registry.get_devices_for_task_type("HEAVY_PROCESS_VIDEO")
            assert len(heavy_devices) == 1
            assert heavy_devices[0].hostname == "rtx-4090-1"

    def test_all_devices_listing(self, mock_sessions):
        """Test listing all registered devices regardless of status."""
        _, device_session = mock_sessions
        registry = DeviceRegistry(device_session)

        # Setup multiple devices with different statuses
        device1 = MagicMock()
        device1.hostname = "device-a"
        device1.device_type = "jetson_coral"

        device2 = MagicMock()
        device2.hostname = "device-b"
        device2.device_type = "rtx_4090"

        with patch.object(device_session, 'query') as mock_query:
            mock_query.return_value.order_by.return_value.all.return_value = [
                device1,
                device2
            ]

            all_devices = registry.list_all_devices()
            assert len(all_devices) == 2

    def test_device_count_by_type(self, mock_sessions):
        """Test counting devices by type."""
        _, device_session = mock_sessions
        registry = DeviceRegistry(device_session)

        with patch.object(device_session, 'query') as mock_query:
            mock_query.return_value.filter.return_value.count.return_value = 3

            count = registry.get_device_count(device_type="jetson_coral")
            assert count == 3

    def test_device_capability_requirements(self, mock_sessions):
        """Test that device capabilities are properly stored and retrieved."""
        _, device_session = mock_sessions
        registry = DeviceRegistry(device_session)

        # Register a device with complex capabilities
        device = registry.register_device(
            hostname="rtx-4090-workstation",
            device_type="rtx_4090",
            capabilities={
                "gpu": {
                    "model": "RTX 4090",
                    "vram_gb": 24,
                    "cores": 16384
                },
                "cpu": {
                    "model": "Intel i9-13900K",
                    "cores": 24,
                    "threads": 32
                },
                "memory_gb": 32,
                "storage_tb": 2,
                "network_mbps": 1000
            }
        )

        assert device.capabilities["gpu"]["model"] == "RTX 4090"
        assert device.capabilities["cpu"]["cores"] == 24

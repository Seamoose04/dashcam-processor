"""Unit tests for DeviceRegistry service."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from src.models.device import Device
from services.device_registry import DeviceRegistry

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    return session

class TestDeviceRegistry:
    """Test cases for DeviceRegistry."""

    def test_register_device_new(self, mock_db_session):
        """Test registering a new device."""
        registry = DeviceRegistry(mock_db_session)

        device = registry.register_device(
            hostname="jetson-coral-1",
            device_type="jetson_coral",
            capabilities={"gpu": "NVIDIA Jetson", "memory_gb": 4}
        )

        assert device.hostname == "jetson-coral-1"
        assert device.device_type == "jetson_coral"
        assert device.status == "online"
        assert device.capabilities["gpu"] == "NVIDIA Jetson"

    def test_register_device_existing(self, mock_db_session):
        """Test updating an existing device."""
        registry = DeviceRegistry(mock_db_session)

        # Setup existing device
        existing_device = MagicMock(spec=Device)
        existing_device.hostname = "rtx-4090-1"
        existing_device.device_type = "old_type"

        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_device

        result = registry.register_device(
            hostname="rtx-4090-1",
            device_type="rtx_4090",
            capabilities={"gpu": "RTX 4090"}
        )

        assert result is existing_device
        assert existing_device.device_type == "rtx_4090"
        assert existing_device.status == "online"

    def test_register_device_invalid_type(self, mock_db_session):
        """Test registering a device with invalid type."""
        registry = DeviceRegistry(mock_db_session)

        with pytest.raises(ValueError) as exc_info:
            registry.register_device(
                hostname="test-device",
                device_type="INVALID_TYPE",
                capabilities={}
            )

        assert "Invalid device_type" in str(exc_info.value)

    def test_update_heartbeat(self, mock_db_session):
        """Test updating device heartbeat."""
        registry = DeviceRegistry(mock_db_session)

        device = MagicMock(spec=Device)
        device.hostname = "indoor-nas-1"
        device.status = "offline"

        mock_db_session.query.return_value.filter.return_value.first.return_value = device

        result = registry.update_heartbeat("indoor-nas-1")

        assert result is True
        assert device.status == "online"

    def test_update_heartbeat_unknown_device(self, mock_db_session):
        """Test updating heartbeat for unknown device."""
        registry = DeviceRegistry(mock_db_session)

        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = registry.update_heartbeat("unknown-device")

        assert result is False

    def test_mark_device_offline(self, mock_db_session):
        """Test marking a device as offline."""
        registry = DeviceRegistry(mock_db_session)

        device = MagicMock(spec=Device)
        device.hostname = "shed-nas-1"
        device.status = "online"

        mock_db_session.query.return_value.filter.return_value.first.return_value = device

        result = registry.mark_device_offline("shed-nas-1")

        assert result is True
        assert device.status == "offline"

    def test_mark_device_offline_not_found(self, mock_db_session):
        """Test marking a non-existent device as offline."""
        registry = DeviceRegistry(mock_db_session)

        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = registry.mark_device_offline("unknown-device")

        assert result is False

    def test_get_device_by_hostname(self, mock_db_session):
        """Test getting a device by hostname."""
        registry = DeviceRegistry(mock_db_session)

        device = MagicMock(spec=Device)
        device.hostname = "jetson-coral-1"
        device.device_type = "jetson_coral"

        mock_db_session.query.return_value.filter.return_value.first.return_value = device

        result = registry.get_device_by_hostname("jetson-coral-1")

        assert result is not None
        assert result.hostname == "jetson-coral-1"

    def test_get_device_by_hostname_not_found(self, mock_db_session):
        """Test getting a non-existent device."""
        registry = DeviceRegistry(mock_db_session)

        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = registry.get_device_by_hostname("unknown-device")
        assert result is None

    def test_get_devices_by_type(self, mock_db_session):
        """Test getting devices by type."""
        registry = DeviceRegistry(mock_db_session)

        device1 = MagicMock(spec=Device)
        device1.hostname = "jetson-coral-1"
        device1.device_type = "jetson_coral"

        device2 = MagicMock(spec=Device)
        device2.hostname = "jetson-coral-2"
        device2.device_type = "jetson_coral"

        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            device1,
            device2
        ]

        devices = registry.get_devices_by_type("jetson_coral")

        assert len(devices) == 2

    def test_get_online_devices(self, mock_db_session):
        """Test getting online devices."""
        registry = DeviceRegistry(mock_db_session)

        now = datetime.now(timezone.utc)
        recent = now - timedelta(minutes=1)
        old = now - timedelta(minutes=10)

        device1 = MagicMock(spec=Device)
        device1.hostname = "online-device"
        device1.status = "online"
        device1.last_heartbeat = recent

        device2 = MagicMock(spec=Device)
        device2.hostname = "offline-device"
        device2.status = "online"
        device2.last_heartbeat = old

        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            device1,
            device2
        ]

        devices = registry.get_online_devices()

        assert len(devices) == 1
        assert devices[0].hostname == "online-device"

    def test_get_devices_for_task_type(self, mock_db_session):
        """Test getting devices capable of handling a task type."""
        registry = DeviceRegistry(mock_db_session)

        jetson_device = MagicMock(spec=Device)
        jetson_device.hostname = "jetson-coral-1"
        jetson_device.device_type = "jetson_coral"
        jetson_device.status = "online"

        rtx_device = MagicMock(spec=Device)
        rtx_device.hostname = "rtx-4090-1"
        rtx_device.device_type = "rtx_4090"
        rtx_device.status = "online"

        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            jetson_device
        ]

        # PREPROCESS_VIDEO should only match jetson_coral devices
        devices = registry.get_devices_for_task_type("PREPROCESS_VIDEO")

        assert len(devices) == 1
        assert devices[0].hostname == "jetson-coral-1"

    def test_list_all_devices(self, mock_db_session):
        """Test listing all registered devices."""
        registry = DeviceRegistry(mock_db_session)

        device1 = MagicMock(spec=Device)
        device1.hostname = "device-a"
        device1.device_type = "jetson_coral"

        device2 = MagicMock(spec=Device)
        device2.hostname = "device-b"
        device2.device_type = "rtx_4090"

        mock_db_session.query.return_value.order_by.return_value.all.return_value = [
            device1,
            device2
        ]

        devices = registry.list_all_devices()

        assert len(devices) == 2

    def test_get_device_count(self, mock_db_session):
        """Test getting device count."""
        registry = DeviceRegistry(mock_db_session)

        mock_db_session.query.return_value.filter.return_value.count.return_value = 3

        count = registry.get_device_count(device_type="jetson_coral")

        assert count == 3
"""Device Registry - System for device registration and capability tracking."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.device import Device

logger = logging.getLogger(__name__)

class DeviceRegistry:
    """Central registry for tracking devices and their capabilities."""

    def __init__(self, db_session: Session):
        """Initialize DeviceRegistry with database session.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session

    def register_device(
        self,
        hostname: str,
        device_type: str,
        capabilities: Dict[str, Any]
    ) -> Device:
        """Register a new device or update existing registration.

        Args:
            hostname: Device hostname (must be unique)
            device_type: Type of device (jetson_coral, rtx_4090, etc.)
            capabilities: Hardware capabilities dictionary

        Returns:
            Registered/updated Device object

        Raises:
            ValueError: If device_type is invalid
        """
        valid_types = {
            "dashcam",
            "indoor_nas",
            "jetson_coral",
            "main_server",
            "rtx_4090",
            "shed_nas"
        }
        if device_type not in valid_types:
            raise ValueError(f"Invalid device_type: {device_type}. Valid types: {valid_types}")

        # Check if device already exists
        existing = self.db_session.query(Device).filter(
            Device.hostname == hostname
        ).first()

        now = datetime.utcnow()

        if existing:
            # Update existing device
            existing.device_type = device_type
            existing.capabilities = capabilities
            existing.status = "online"
            existing.last_heartbeat = now
            logger.info(f"Updated registration for device {hostname}")
        else:
            # Create new device
            device = Device(
                hostname=hostname,
                device_type=device_type,
                status="online",
                last_heartbeat=now,
                capabilities=capabilities
            )
            self.db_session.add(device)
            logger.info(f"Registered new device {hostname} of type {device_type}")

        try:
            self.db_session.commit()
            return existing if existing else device
        except IntegrityError as e:
            self.db_session.rollback()
            logger.error(f"Failed to register device: {e}")
            raise

    def update_heartbeat(self, hostname: str) -> bool:
        """Update heartbeat timestamp for a device.

        Args:
            hostname: Device hostname

        Returns:
            True if updated successfully, False otherwise
        """
        device = self.db_session.query(Device).filter(
            Device.hostname == hostname
        ).first()

        if not device:
            logger.warning(f"Heartbeat from unknown device: {hostname}")
            return False

        device.last_heartbeat = datetime.utcnow()
        device.status = "online"

        try:
            self.db_session.commit()
            return True
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to update heartbeat: {e}")
            return False

    def mark_device_offline(self, hostname: str) -> bool:
        """Mark a device as offline.

        Args:
            hostname: Device hostname

        Returns:
            True if marked successfully, False otherwise
        """
        device = self.db_session.query(Device).filter(
            Device.hostname == hostname
        ).first()

        if not device:
            return False

        device.status = "offline"

        try:
            self.db_session.commit()
            return True
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to mark device offline: {e}")
            return False

    def get_device_by_hostname(self, hostname: str) -> Optional[Device]:
        """Get a device by its hostname.

        Args:
            hostname: Device hostname

        Returns:
            Device object or None if not found
        """
        return self.db_session.query(Device).filter(
            Device.hostname == hostname
        ).first()

    def get_devices_by_type(self, device_type: str) -> List[Device]:
        """Get all devices of a specific type.

        Args:
            device_type: Type of device to filter by

        Returns:
            List of matching Device objects
        """
        return self.db_session.query(Device).filter(
            Device.device_type == device_type
        ).all()

    def get_online_devices(self) -> List[Device]:
        """Get all devices currently marked as online.

        Returns:
            List of online Device objects
        """
        # Consider a device offline if no heartbeat in last 5 minutes
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        return self.db_session.query(Device).filter(
            (Device.status == "online") &
            (Device.last_heartbeat >= cutoff)
        ).all()

    def get_devices_for_task_type(self, task_type: str) -> List[Device]:
        """Get devices capable of handling a specific task type.

        Args:
            task_type: Task type to filter by

        Returns:
            List of eligible Device objects
        """
        # Map task types to device types based on architectural blueprint
        task_to_device = {
            "INGEST_VIDEO": ["indoor_nas", "main_server"],
            "PREPROCESS_VIDEO": ["jetson_coral"],
            "HEAVY_PROCESS_VIDEO": ["rtx_4090"],
            "ARCHIVE_VIDEO": ["shed_nas"]
        }

        eligible_device_types = task_to_device.get(task_type, [])

        if not eligible_device_types:
            return []

        return self.db_session.query(Device).filter(
            Device.device_type.in_(eligible_device_types),
            Device.status == "online"
        ).all()

    def list_all_devices(self) -> List[Device]:
        """List all registered devices.

        Returns:
            List of all Device objects
        """
        return self.db_session.query(Device).order_by(
            Device.hostname
        ).all()

    def get_device_count(self, device_type: Optional[str] = None) -> int:
        """Get count of devices matching criteria.

        Args:
            device_type: Filter by specific device type

        Returns:
            Count of matching devices
        """
        query = self.db_session.query(Device)

        if device_type:
            query = query.filter(Device.device_type == device_type)

        return query.count()
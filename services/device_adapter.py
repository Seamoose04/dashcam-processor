"""Abstract Device Adapter - Base class for all device-specific adapters."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class DeviceAdapter(ABC):
    """Abstract base class for all device adapters."""

    def __init__(self, hostname: str, config: Dict[str, Any]):
        """Initialize device adapter.

        Args:
            hostname: Unique identifier for this device
            config: Device-specific configuration
        """
        self.hostname = hostname
        self.config = config
        self.device_type = self._get_device_type()
        self.capabilities = self.get_device_capabilities()

    @abstractmethod
    def _get_device_type(self) -> str:
        """Get the device type identifier.

        Returns:
            Device type string (e.g., 'jetson_coral', 'rtx_4090')
        """
        pass

    @abstractmethod
    def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Pull pending tasks of specified type.

        Args:
            task_type: Filter by specific task type
            limit: Maximum number of tasks to pull

        Returns:
            List of task dictionaries that are pending and match criteria
        """
        pass

    @abstractmethod
    def mark_task_complete(
        self,
        task_id: int,
        new_tasks: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Mark task as complete and optionally publish new tasks.

        Args:
            task_id: ID of the task to complete
            new_tasks: List of new tasks to create (downstream work)

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_device_capabilities(self) -> Dict[str, Any]:
        """Return device hardware capabilities.

        Returns:
            Dictionary containing capability information
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verify device is operational.

        Returns:
            True if device is healthy, False otherwise
        """
        pass

    def execute_task_loop(self):
        """Main execution loop for pulling and processing tasks."""
        while True:
            try:
                # Check device health before pulling tasks
                if not self.health_check():
                    logger.warning(f"Device {self.hostname} health check failed")
                    break

                # Pull tasks based on device capabilities
                tasks = self.get_pending_tasks(limit=1)

                if not tasks:
                    # No tasks available, wait and retry
                    logger.debug(f"No tasks available for {self.device_type}, waiting...")
                    continue

                task = tasks[0]
                logger.info(
                    f"Device {self.hostname} pulled task {task['task_id']} "
                    f"of type {task['task_type']}"
                )

                # Execute the task (implementation specific)
                success = self._execute_task(task)

                if success:
                    # Mark task as complete
                    self.mark_task_complete(
                        task['task_id'],
                        new_tasks=self._get_downstream_tasks(task)
                    )
                else:
                    logger.error(f"Failed to execute task {task['task_id']}")

            except Exception as e:
                logger.error(f"Error in task loop: {e}")
                # Implement retry logic or graceful shutdown

    @abstractmethod
    def _execute_task(self, task: Dict[str, Any]) -> bool:
        """Execute a specific task (implementation specific).

        Args:
            task: Task dictionary to execute

        Returns:
            True if execution succeeded, False otherwise
        """
        pass

    @abstractmethod
    def _get_downstream_tasks(
        self,
        completed_task: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Get downstream tasks to create after completing a task.

        Args:
            completed_task: Task that was just completed

        Returns:
            List of new task dictionaries or None
        """
        pass
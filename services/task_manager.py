"""Task Manager - Core class handling task creation, distribution, and completion."""

from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.task import Task, InputOutput
from models.device import Device

logger = logging.getLogger(__name__)

class TaskManager:
    """Central task coordinator for the dashcam processor pipeline."""

    def __init__(self, db_session: Session):
        """Initialize TaskManager with database session.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session

    def create_task(
        self,
        task_type: str,
        video_id: Optional[str] = None,
        inputs: Optional[List[Dict[str, Any]]] = None,
        outputs: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        device_capabilities_required: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Create a new task in the pending state.

        Args:
            task_type: Type of task (INGEST_VIDEO, PREPROCESS_VIDEO, etc.)
            video_id: ID of the video being processed (optional)
            inputs: List of input file references
            outputs: List of expected output file references
            metadata: Task-specific metadata
            device_capabilities_required: Hardware requirements for this task

        Returns:
            Created Task object

        Raises:
            ValueError: If task_type is invalid or required fields are missing
        """
        if not task_type:
            raise ValueError("task_type is required")

        # Validate task type against known types
        valid_types = {
            "INGEST_VIDEO",
            "PREPROCESS_VIDEO",
            "HEAVY_PROCESS_VIDEO",
            "ARCHIVE_VIDEO"
        }
        if task_type not in valid_types:
            raise ValueError(f"Invalid task_type: {task_type}. Valid types: {valid_types}")

        task = Task(
            task_type=task_type,
            state="pending",
            created_at=datetime.utcnow(),
            video_id=video_id,
            inputs=inputs or [],
            outputs=outputs or [],
            metadata=metadata or {},
            device_capabilities_required=device_capabilities_required or {}
        )

        self.db_session.add(task)
        try:
            self.db_session.commit()
            logger.info(f"Created task {task.task_id} of type {task_type}")
            return task
        except IntegrityError as e:
            self.db_session.rollback()
            logger.error(f"Failed to create task: {e}")
            raise

    def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        limit: int = 1,
        device_capabilities: Optional[Dict[str, Any]] = None
    ) -> List[Task]:
        """Get pending tasks matching criteria (pull-based execution).

        Args:
            task_type: Filter by specific task type
            limit: Maximum number of tasks to return
            device_capabilities: Device capabilities for filtering

        Returns:
            List of Task objects that are pending and match criteria
        """
        query = self.db_session.query(Task).filter(
            Task.state == "pending"
        )

        if task_type:
            query = query.filter(Task.task_type == task_type)

        # Filter by device capabilities if provided
        if device_capabilities:
            query = query.filter(
                ~Task.device_capabilities_required.has_any(
                    **device_capabilities
                ) | (
                    Task.device_capabilities_required == None
                )
            )

        tasks = query.order_by(Task.created_at).limit(limit).all()

        logger.debug(f"Found {len(tasks)} pending tasks matching criteria")
        return tasks

    def mark_task_complete(
        self,
        task_id: int,
        new_tasks: Optional[List[Dict[str, Any]]] = None
    ) -> Task:
        """Mark a task as complete and optionally publish new downstream tasks.

        Args:
            task_id: ID of the task to complete
            new_tasks: List of new tasks to create (downstream work)

        Returns:
            Updated Task object

        Raises:
            ValueError: If task not found or already completed
        """
        task = self.db_session.query(Task).get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.state == "complete":
            raise ValueError(f"Task {task_id} is already complete")

        # Update task state and completion time
        task.state = "complete"
        task.completed_at = datetime.utcnow()

        # Create new tasks if provided
        created_tasks = []
        if new_tasks:
            for new_task_data in new_tasks:
                try:
                    new_task = self.create_task(**new_task_data)
                    created_tasks.append(new_task)
                except Exception as e:
                    logger.warning(f"Failed to create downstream task: {e}")
                    # Continue with other tasks even if one fails

        try:
            self.db_session.commit()
            logger.info(
                f"Marked task {task_id} of type {task.task_type} as complete. "
                f"Created {len(created_tasks)} new tasks."
            )
            return task
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to mark task complete: {e}")
            raise

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """Get a specific task by ID.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Task object or None if not found
        """
        return self.db_session.query(Task).get(task_id)

    def list_tasks(
        self,
        task_type: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Task]:
        """List tasks with optional filtering.

        Args:
            task_type: Filter by task type
            state: Filter by state (pending/complete)
            limit: Maximum number of tasks to return
            offset: Pagination offset

        Returns:
            List of Task objects
        """
        query = self.db_session.query(Task)

        if task_type:
            query = query.filter(Task.task_type == task_type)

        if state:
            query = query.filter(Task.state == state)

        return query.order_by(Task.created_at).limit(limit).offset(offset).all()

    def get_task_count(
        self,
        task_type: Optional[str] = None,
        state: Optional[str] = None
    ) -> int:
        """Get count of tasks matching criteria.

        Args:
            task_type: Filter by task type
            state: Filter by state

        Returns:
            Count of matching tasks
        """
        query = self.db_session.query(Task)

        if task_type:
            query = query.filter(Task.task_type == task_type)

        if state:
            query = query.filter(Task.state == state)

        return query.count()
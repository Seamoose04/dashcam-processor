"""REST API endpoints for task management."""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional

from models.task import Task
from services.task_manager import TaskManager
from services.device_registry import DeviceRegistry

router = APIRouter(prefix="/api/v1", tags=["tasks"])

# Dependency to get task manager instance
def get_task_manager() -> TaskManager:
    """Get TaskManager instance (to be replaced with actual dependency injection)."""
    # In production, this would use proper DI or factory pattern
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///tasks.db")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = SessionLocal()

    try:
        yield TaskManager(db_session)
    finally:
        db_session.close()

# Dependency to get device registry instance
def get_device_registry() -> DeviceRegistry:
    """Get DeviceRegistry instance (to be replaced with actual dependency injection)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///tasks.db")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = SessionLocal()

    try:
        yield DeviceRegistry(db_session)
    finally:
        db_session.close()

@router.get("/tasks", response_model=List[dict])
async def list_tasks(
    task_type: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    task_manager: TaskManager = Depends(get_task_manager)
) -> List[dict]:
    """List tasks with optional filtering.

    Args:
        task_type: Filter by task type
        state: Filter by state (pending/complete)
        limit: Maximum number of tasks to return
        offset: Pagination offset

    Returns:
        List of task dictionaries
    """
    try:
        tasks = task_manager.list_tasks(
            task_type=task_type,
            state=state,
            limit=limit,
            offset=offset
        )
        return [task.to_dict() for task in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{task_id}", response_model=dict)
async def get_task(
    task_id: int,
    task_manager: TaskManager = Depends(get_task_manager)
) -> dict:
    """Get a specific task by ID.

    Args:
        task_id: Task ID to retrieve

    Returns:
        Task dictionary

    Raises:
        HTTPException 404: If task not found
    """
    try:
        task = task_manager.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return task.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks", response_model=dict, status_code=201)
async def create_task(
    task_data: dict,
    task_manager: TaskManager = Depends(get_task_manager)
) -> dict:
    """Create a new task.

    Args:
        task_data: Task creation payload

    Returns:
        Created task dictionary

    Raises:
        HTTPException 400: If validation fails
        HTTPException 500: If task creation fails
    """
    try:
        required_fields = ["task_type"]
        for field in required_fields:
            if field not in task_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )

        task = task_manager.create_task(**task_data)
        return task.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/{task_id}/complete", response_model=dict)
async def mark_task_complete(
    task_id: int,
    new_tasks: Optional[List[dict]] = None,
    task_manager: TaskManager = Depends(get_task_manager)
) -> dict:
    """Mark a task as complete and optionally publish new downstream tasks.

    Args:
        task_id: ID of the task to complete
        new_tasks: List of new tasks to create

    Returns:
        Success message dictionary

    Raises:
        HTTPException 404: If task not found
        HTTPException 400: If validation fails
        HTTPException 500: If operation fails
    """
    try:
        task = task_manager.mark_task_complete(
            task_id=task_id,
            new_tasks=new_tasks or []
        )

        return {
            "message": f"Task {task_id} marked as complete",
            "task_type": task.task_type,
            "completed_at": task.completed_at.isoformat(),
            "new_tasks_created": len(new_tasks or [])
        }
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "already complete" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/pending", response_model=List[dict])
async def get_pending_tasks(
    task_type: Optional[str] = Query(None),
    limit: int = Query(1, ge=1, le=100),
    device_capabilities: Optional[dict] = None,
    task_manager: TaskManager = Depends(get_task_manager)
) -> List[dict]:
    """Get pending tasks for pull-based execution.

    This is the main endpoint used by worker devices to pull tasks.

    Args:
        task_type: Filter by specific task type
        limit: Maximum number of tasks to return (default 1)
        device_capabilities: Device capabilities for filtering

    Returns:
        List of pending task dictionaries
    """
    try:
        tasks = task_manager.get_pending_tasks(
            task_type=task_type,
            limit=limit,
            device_capabilities=device_capabilities
        )

        if not tasks:
            raise HTTPException(status_code=404, detail="No tasks pending")

        return [task.to_dict() for task in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
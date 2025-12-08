from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas import TaskPullRequest, TaskPullResponse, TaskCompleteRequest, IngestionRequest
from src.core.services import TaskService
from src.db.session import get_session

router = APIRouter()


def get_task_service(session=Depends(get_session)) -> TaskService:
    return TaskService(session=session)


@router.post("/tasks/pull", response_model=TaskPullResponse)
def pull_task(payload: TaskPullRequest, service: TaskService = Depends(get_task_service)):
    task = service.pull_task(device_class=payload.device_class)
    if not task:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT, detail="No tasks available")
    return TaskPullResponse.from_model(task)


@router.post("/tasks/complete")
def complete_task(payload: TaskCompleteRequest, service: TaskService = Depends(get_task_service)):
    service.complete_task(task_id=payload.task_id, spawn=payload.spawn)
    return {"status": "ok"}


@router.post("/ingestion")
def create_ingestion(payload: IngestionRequest, service: TaskService = Depends(get_task_service)):
    service.create_ingestion_task(video_id=payload.video_id, device=payload.device, path=payload.path)
    return {"status": "ok"}

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.container import AppContainer, get_container
from app.exceptions import InvalidCircuitError, QueuePublishError
from app.schemas import SubmitTaskRequest, SubmitTaskResponse
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_service(container: AppContainer = Depends(get_container)) -> TaskService:
    return container.task_service


@router.post("", response_model=SubmitTaskResponse, status_code=202)
def submit_task(
    body: SubmitTaskRequest,
    service: TaskService = Depends(get_task_service),
) -> SubmitTaskResponse | JSONResponse:
    try:
        task_id = service.submit(body.qc)
    except InvalidCircuitError as exc:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": str(exc)},
        )
    except QueuePublishError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Failed to enqueue task."},
        )
    return SubmitTaskResponse(task_id=task_id, message="Task submitted successfully.")


@router.get("/{task_id}")
def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> JSONResponse:
    payload, status_code = service.get_status_payload(task_id)
    return JSONResponse(status_code=status_code, content=payload)

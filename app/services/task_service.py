from __future__ import annotations

from uuid import UUID

import structlog

from app.domain.task import Task, TaskStatus
from app.exceptions import InvalidCircuitError, QueuePublishError
from app.interfaces import CircuitRunner, QueuePublisher, TaskRepository
from app import metrics

logger = structlog.get_logger(__name__)


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
        publisher: QueuePublisher,
        circuit_runner: CircuitRunner,
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._circuit_runner = circuit_runner

    def submit(self, qasm: str) -> str:
        self._circuit_runner.validate(qasm)
        task = Task(qc=qasm)
        self._repository.save(task)
        try:
            self._publisher.publish(str(task.id))
        except Exception as exc:
            metrics.QUEUE_PUBLISH_ERRORS.inc()
            task.fail("Failed to enqueue task for processing.")
            self._repository.update(task)
            logger.error("queue_publish_failed", task_id=str(task.id), error=str(exc))
            raise QueuePublishError("Failed to enqueue task.") from exc

        metrics.TASKS_SUBMITTED.inc()
        logger.info("task_submitted", task_id=str(task.id), qasm_length=len(qasm))
        return str(task.id)

    def get(self, task_id: str) -> Task | None:
        try:
            uid = UUID(task_id)
        except ValueError:
            return None
        return self._repository.get(uid)

    def get_status_payload(self, task_id: str) -> tuple[dict, int]:
        task = self.get(task_id)
        if task is None:
            return {"status": "error", "message": "Task not found."}, 404
        if task.status is TaskStatus.COMPLETED:
            return {"status": "completed", "result": task.result or {}}, 200
        if task.status is TaskStatus.FAILED:
            return {
                "status": "failed",
                "message": task.error_message or "Task failed.",
            }, 200
        return {"status": "pending", "message": "Task is still in progress."}, 200

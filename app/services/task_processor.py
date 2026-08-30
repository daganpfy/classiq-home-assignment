from __future__ import annotations

from uuid import UUID

import structlog

from app.domain.task import TaskStatus
from app.exceptions import (
    InvalidCircuitError,
    InvalidTransitionError,
    PermanentProcessingError,
    TaskNotFoundError,
)
from app.interfaces import CircuitRunner, TaskRepository
from app import metrics

logger = structlog.get_logger(__name__)


class TaskProcessor:
    def __init__(self, repository: TaskRepository, circuit_runner: CircuitRunner) -> None:
        self._repository = repository
        self._circuit_runner = circuit_runner

    def process(self, task_id: str) -> None:
        task = self._load(task_id)
        if task.status is TaskStatus.COMPLETED:
            logger.info("task_already_completed", task_id=task_id)
            return
        if task.status is TaskStatus.FAILED:
            logger.info("task_already_failed", task_id=task_id)
            return

        with metrics.TASK_PROCESSING_SECONDS.time():
            try:
                result = self._circuit_runner.execute(task.qc)
            except InvalidCircuitError as exc:
                self._fail(task, str(exc), reason="invalid_circuit")
                raise PermanentProcessingError(str(exc)) from exc
            except Exception:
                raise

        try:
            task.complete(result)
        except InvalidTransitionError:
            logger.info("task_race_already_terminal", task_id=task_id)
            return
        self._repository.update(task)
        metrics.TASKS_COMPLETED.inc()
        logger.info("task_completed", task_id=task_id, shots=sum(result.values()))

    def record_retry(self, task_id: str) -> None:
        task = self._load(task_id)
        if task.status is not TaskStatus.PENDING:
            return
        task.record_retry()
        self._repository.update(task)
        metrics.TASKS_RETRIED.inc()
        logger.warning("task_retry_scheduled", task_id=task_id, retry_count=task.retry_count)

    def fail_permanently(self, task_id: str, message: str) -> None:
        task = self._load(task_id)
        if task.status is not TaskStatus.PENDING:
            return
        self._fail(task, message, reason="exhausted_retries")

    def _fail(self, task, message: str, reason: str) -> None:
        task.fail(message)
        self._repository.update(task)
        metrics.TASKS_FAILED.labels(reason=reason).inc()
        metrics.TASKS_DLQ.inc()
        logger.error("task_failed", task_id=str(task.id), reason=reason, error=message)

    def _load(self, task_id: str):
        try:
            uid = UUID(task_id)
        except ValueError as exc:
            raise PermanentProcessingError(f"Invalid task id: {task_id}") from exc
        task = self._repository.get(uid)
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found.")
        return task

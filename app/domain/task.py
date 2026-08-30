from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from app.exceptions import InvalidTransitionError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


_ALLOWED: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
}


@dataclass
class Task:
    qc: str
    id: UUID = field(default_factory=uuid4)
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, int] | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def _transition(self, target: TaskStatus) -> None:
        allowed = _ALLOWED[self.status]
        if target not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self.status.value} to {target.value}."
            )
        self.status = target
        self.updated_at = _utcnow()

    def complete(self, result: dict[str, int]) -> None:
        self._transition(TaskStatus.COMPLETED)
        self.result = result
        self.error_message = None

    def fail(self, message: str) -> None:
        self._transition(TaskStatus.FAILED)
        self.error_message = message

    def record_retry(self) -> None:
        if self.status is not TaskStatus.PENDING:
            raise InvalidTransitionError(
                f"Cannot retry a task in status {self.status.value}."
            )
        self.retry_count += 1
        self.updated_at = _utcnow()

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.task import Task


class TaskRepository(Protocol):
    def save(self, task: Task) -> None: ...

    def get(self, task_id: UUID) -> Task | None: ...

    def update(self, task: Task) -> None: ...


class QueuePublisher(Protocol):
    def publish(self, task_id: str) -> None: ...


class CircuitRunner(Protocol):
    def validate(self, qasm: str) -> None: ...

    def execute(self, qasm: str) -> dict[str, int]: ...

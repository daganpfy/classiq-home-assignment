from __future__ import annotations

from uuid import UUID

import pytest

from app.domain.task import Task, TaskStatus
from app.exceptions import InvalidCircuitError, PermanentProcessingError, QueuePublishError
from app.services.task_processor import TaskProcessor
from app.services.task_service import TaskService


class FakeRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Task] = {}

    def save(self, task: Task) -> None:
        self.rows[task.id] = task

    def get(self, task_id: UUID) -> Task | None:
        return self.rows.get(task_id)

    def update(self, task: Task) -> None:
        self.rows[task.id] = task


class FakePublisher:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[str] = []

    def publish(self, task_id: str) -> None:
        if self.fail:
            raise RuntimeError("broker down")
        self.published.append(task_id)


class FakeRunner:
    def __init__(self, invalid: bool = False, execute_error: Exception | None = None) -> None:
        self.invalid = invalid
        self.execute_error = execute_error
        self.validated: list[str] = []

    def validate(self, qasm: str) -> None:
        if self.invalid:
            raise InvalidCircuitError("bad qasm")
        self.validated.append(qasm)

    def execute(self, qasm: str) -> dict[str, int]:
        if self.execute_error:
            raise self.execute_error
        return {"0": 512, "1": 512}


def test_submit_persists_pending_and_enqueues() -> None:
    repo = FakeRepository()
    publisher = FakePublisher()
    service = TaskService(repo, publisher, FakeRunner())

    task_id = service.submit("qasm")

    stored = repo.get(UUID(task_id))
    assert stored is not None
    assert stored.status is TaskStatus.PENDING
    assert publisher.published == [task_id]


def test_submit_rejects_invalid_circuit_before_persist() -> None:
    repo = FakeRepository()
    publisher = FakePublisher()
    service = TaskService(repo, publisher, FakeRunner(invalid=True))

    with pytest.raises(InvalidCircuitError):
        service.submit("nope")

    assert repo.rows == {}
    assert publisher.published == []


def test_submit_marks_failed_if_enqueue_fails() -> None:
    repo = FakeRepository()
    publisher = FakePublisher(fail=True)
    service = TaskService(repo, publisher, FakeRunner())

    with pytest.raises(QueuePublishError):
        service.submit("qasm")

    stored = next(iter(repo.rows.values()))
    assert stored.status is TaskStatus.FAILED


def test_get_unknown_id_is_not_found() -> None:
    service = TaskService(FakeRepository(), FakePublisher(), FakeRunner())
    payload, status = service.get_status_payload("not-a-uuid")
    assert status == 404
    assert payload == {"status": "error", "message": "Task not found."}


def test_get_pending_matches_assignment_shape() -> None:
    repo = FakeRepository()
    service = TaskService(repo, FakePublisher(), FakeRunner())
    task_id = service.submit("qasm")
    payload, status = service.get_status_payload(task_id)
    assert status == 200
    assert payload == {"status": "pending", "message": "Task is still in progress."}


def test_processor_completes_pending_task() -> None:
    repo = FakeRepository()
    runner = FakeRunner()
    service = TaskService(repo, FakePublisher(), runner)
    task_id = service.submit("qasm")

    TaskProcessor(repo, runner).process(task_id)

    payload, status = service.get_status_payload(task_id)
    assert status == 200
    assert payload == {"status": "completed", "result": {"0": 512, "1": 512}}


def test_processor_is_idempotent_after_completion() -> None:
    repo = FakeRepository()
    runner = FakeRunner()
    task_id = TaskService(repo, FakePublisher(), runner).submit("qasm")
    processor = TaskProcessor(repo, runner)
    processor.process(task_id)
    processor.process(task_id)
    assert repo.get(UUID(task_id)).status is TaskStatus.COMPLETED


def test_processor_invalid_circuit_is_permanent_failure() -> None:
    repo = FakeRepository()
    ok_runner = FakeRunner()
    task_id = TaskService(repo, FakePublisher(), ok_runner).submit("qasm")
    processor = TaskProcessor(repo, FakeRunner(execute_error=InvalidCircuitError("bad")))

    with pytest.raises(PermanentProcessingError):
        processor.process(task_id)

    stored = repo.get(UUID(task_id))
    assert stored.status is TaskStatus.FAILED

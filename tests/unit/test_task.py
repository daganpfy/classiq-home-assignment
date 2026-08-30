from __future__ import annotations

import pytest

from app.domain.task import Task, TaskStatus
from app.exceptions import InvalidTransitionError


def test_new_task_starts_pending() -> None:
    task = Task(qc="OPENQASM 3;")
    assert task.status is TaskStatus.PENDING
    assert task.result is None
    assert task.retry_count == 0


def test_pending_to_completed() -> None:
    task = Task(qc="q")
    task.complete({"0": 512, "1": 512})
    assert task.status is TaskStatus.COMPLETED
    assert task.result == {"0": 512, "1": 512}
    assert task.error_message is None


def test_pending_to_failed() -> None:
    task = Task(qc="q")
    task.fail("boom")
    assert task.status is TaskStatus.FAILED
    assert task.error_message == "boom"


def test_retry_only_from_pending() -> None:
    task = Task(qc="q")
    task.record_retry()
    assert task.retry_count == 1


def test_completed_cannot_fail() -> None:
    task = Task(qc="q")
    task.complete({"0": 1})
    with pytest.raises(InvalidTransitionError):
        task.fail("nope")


def test_failed_cannot_complete() -> None:
    task = Task(qc="q")
    task.fail("nope")
    with pytest.raises(InvalidTransitionError):
        task.complete({"0": 1})


def test_completed_cannot_retry() -> None:
    task = Task(qc="q")
    task.complete({"0": 1})
    with pytest.raises(InvalidTransitionError):
        task.record_retry()

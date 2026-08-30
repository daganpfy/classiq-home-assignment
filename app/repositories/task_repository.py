from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.domain.task import Task, TaskStatus
from app.repositories.models import TaskRow


def _to_domain(row: TaskRow) -> Task:
    result = None
    if row.result is not None:
        result = {str(k): int(v) for k, v in row.result.items()}
    return Task(
        id=row.id,
        qc=row.qc,
        status=TaskStatus(row.status),
        result=result,
        error_message=row.error_message,
        retry_count=row.retry_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _apply(row: TaskRow, task: Task) -> None:
    row.status = task.status.value
    row.qc = task.qc
    row.result = task.result
    row.error_message = task.error_message
    row.retry_count = task.retry_count
    row.created_at = task.created_at
    row.updated_at = task.updated_at


class PostgresTaskRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, task: Task) -> None:
        row = TaskRow(
            id=task.id,
            status=task.status.value,
            qc=task.qc,
            result=task.result,
            error_message=task.error_message,
            retry_count=task.retry_count,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()

    def get(self, task_id: UUID) -> Task | None:
        with self._session_factory() as session:
            row = session.get(TaskRow, task_id)
            if row is None:
                return None
            return _to_domain(row)

    def update(self, task: Task) -> None:
        with self._session_factory() as session:
            row = session.get(TaskRow, task.id)
            if row is None:
                return
            _apply(row, task)
            session.commit()

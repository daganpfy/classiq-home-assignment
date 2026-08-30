from __future__ import annotations

import structlog
from celery import Celery

from app.exceptions import QueuePublishError

logger = structlog.get_logger(__name__)


class CeleryQueuePublisher:
    def __init__(self, celery_app: Celery, task_name: str) -> None:
        self._celery_app = celery_app
        self._task_name = task_name

    def publish(self, task_id: str) -> None:
        try:
            self._celery_app.send_task(self._task_name, args=[task_id], queue="tasks")
        except Exception as exc:
            logger.error("broker_publish_failed", task_id=task_id, error=str(exc))
            raise QueuePublishError(str(exc)) from exc

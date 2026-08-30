from __future__ import annotations

from celery.exceptions import MaxRetriesExceededError, Reject
from celery.signals import worker_process_init, worker_ready
from prometheus_client import start_http_server

from app.config import get_settings
from app.container import get_container
from app.exceptions import PermanentProcessingError, TaskNotFoundError
from app.logging import configure_logging
from app.queue.celery_app import celery_app

app = celery_app
settings = get_settings()
configure_logging(settings.log_level)


@worker_process_init.connect
def _configure_worker_logging(**_kwargs) -> None:
    configure_logging(settings.log_level)


@worker_ready.connect
def _start_metrics_server(**_kwargs) -> None:
    start_http_server(settings.metrics_port)


@celery_app.task(
    bind=True,
    name=settings.celery_task_name,
    max_retries=settings.celery_max_retries,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_circuit(self, task_id: str) -> None:
    processor = get_container().task_processor
    try:
        processor.process(task_id)
    except PermanentProcessingError as exc:
        raise Reject(str(exc), requeue=False)
    except TaskNotFoundError as exc:
        try:
            raise self.retry(exc=exc, countdown=min(2**self.request.retries, 8))
        except MaxRetriesExceededError as retry_exc:
            raise Reject(str(exc), requeue=False) from retry_exc
    except Exception as exc:
        processor.record_retry(task_id)
        try:
            raise self.retry(exc=exc, countdown=min(2**self.request.retries, 8))
        except MaxRetriesExceededError as retry_exc:
            processor.fail_permanently(task_id, str(exc))
            raise Reject(str(exc), requeue=False) from retry_exc

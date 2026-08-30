from __future__ import annotations

from kombu import Exchange, Queue

from app.config import get_settings

TASKS_EXCHANGE_NAME = "tasks"
DLX_NAME = "tasks.dlx"
TASKS_QUEUE_NAME = "tasks"
DLQ_NAME = "tasks.dead"
TASKS_ROUTING_KEY = "tasks"
DLQ_ROUTING_KEY = "tasks.dead"

tasks_exchange = Exchange(TASKS_EXCHANGE_NAME, type="direct", durable=True)
dead_letter_exchange = Exchange(DLX_NAME, type="direct", durable=True)

tasks_queue = Queue(
    TASKS_QUEUE_NAME,
    exchange=tasks_exchange,
    routing_key=TASKS_ROUTING_KEY,
    durable=True,
    queue_arguments={
        "x-dead-letter-exchange": DLX_NAME,
        "x-dead-letter-routing-key": DLQ_ROUTING_KEY,
    },
)

dead_letter_queue = Queue(
    DLQ_NAME,
    exchange=dead_letter_exchange,
    routing_key=DLQ_ROUTING_KEY,
    durable=True,
)


def create_celery_app():
    from celery import Celery

    settings = get_settings()
    app = Celery("quantum_jobs")
    app.conf.update(
        broker_url=settings.broker_url,
        result_backend=None,
        task_serializer="json",
        accept_content=["json"],
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_default_queue=TASKS_QUEUE_NAME,
        task_default_exchange=TASKS_EXCHANGE_NAME,
        task_default_routing_key=TASKS_ROUTING_KEY,
        task_queues=(tasks_queue, dead_letter_queue),
        task_routes={settings.celery_task_name: {"queue": TASKS_QUEUE_NAME}},
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = create_celery_app()

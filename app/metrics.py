from __future__ import annotations

from prometheus_client import Counter, Histogram

TASKS_SUBMITTED = Counter(
    "tasks_submitted_total",
    "Quantum circuit tasks accepted by the API.",
)
TASKS_COMPLETED = Counter(
    "tasks_completed_total",
    "Tasks that finished simulation successfully.",
)
TASKS_FAILED = Counter(
    "tasks_failed_total",
    "Tasks that reached a terminal failed state.",
    ["reason"],
)
TASKS_RETRIED = Counter(
    "tasks_retried_total",
    "Worker retries after a transient failure.",
)
TASKS_DLQ = Counter(
    "tasks_dlq_total",
    "Tasks rejected to the dead-letter queue after retries were exhausted.",
)
TASK_PROCESSING_SECONDS = Histogram(
    "task_processing_duration_seconds",
    "Wall time spent executing a circuit on the worker.",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
QUEUE_PUBLISH_ERRORS = Counter(
    "queue_publish_errors_total",
    "API failed to publish a task after persisting it.",
)

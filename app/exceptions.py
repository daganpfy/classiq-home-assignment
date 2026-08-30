from __future__ import annotations


class InvalidCircuitError(Exception):
    """QASM3 payload cannot be parsed or executed."""


class InvalidTransitionError(Exception):
    """Illegal job state-machine transition."""


class TaskNotFoundError(Exception):
    """Worker received a task_id that is not in the store."""


class PermanentProcessingError(Exception):
    """Do not retry; send the message to the DLQ."""


class QueuePublishError(Exception):
    """Broker publish failed after the task row was written."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from kombu import Connection
from sqlalchemy import text

from app.config import Settings
from app.container import AppContainer, get_container

router = APIRouter(tags=["health"])


@router.get("/health")
def health(container: AppContainer = Depends(get_container)) -> dict:
    checks = {
        "postgres": _postgres_ok(container),
        "rabbitmq": _rabbitmq_ok(container.settings),
    }
    status = "ok" if all(checks.values()) else "degraded"
    return {"status": status, "checks": checks}


def _postgres_ok(container: AppContainer) -> bool:
    try:
        with container.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _rabbitmq_ok(settings: Settings) -> bool:
    try:
        with Connection(settings.broker_url) as conn:
            conn.ensure_connection(max_retries=1)
        return True
    except Exception:
        return False

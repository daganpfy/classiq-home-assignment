from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.container import get_container
from app.logging import configure_logging
from app.routers import health, tasks


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_container()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title="Quantum Circuit Task API",
        version="1.0.0",
        lifespan=lifespan,
    )
    Instrumentator().instrument(application).expose(application, endpoint="/metrics")
    application.include_router(tasks.router)
    application.include_router(health.router)
    return application


app = create_app()

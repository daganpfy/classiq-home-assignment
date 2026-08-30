from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.queue.publisher import CeleryQueuePublisher
from app.repositories.models import Base
from app.repositories.task_repository import PostgresTaskRepository
from app.services.circuit_executor import QiskitCircuitExecutor
from app.services.task_processor import TaskProcessor
from app.services.task_service import TaskService


class AppContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )
        from app.queue.celery_app import celery_app

        self.repository = PostgresTaskRepository(self.session_factory)
        self.circuit_runner = QiskitCircuitExecutor(shots=settings.shots)
        self.publisher = CeleryQueuePublisher(celery_app, settings.celery_task_name)
        self.task_service = TaskService(
            repository=self.repository,
            publisher=self.publisher,
            circuit_runner=self.circuit_runner,
        )
        self.task_processor = TaskProcessor(
            repository=self.repository,
            circuit_runner=self.circuit_runner,
        )

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    container = AppContainer(get_settings())
    container.init_db()
    return container

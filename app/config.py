from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://classiq:classiq@postgres:5432/classiq"
    broker_url: str = "amqp://guest:guest@rabbitmq:5672//"
    log_level: str = "INFO"
    shots: int = 1024
    celery_max_retries: int = 3
    metrics_port: int = 9090
    celery_task_name: str = "quantum.process_circuit"


def get_settings() -> Settings:
    return Settings()

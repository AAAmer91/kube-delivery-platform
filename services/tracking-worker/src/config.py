"""Worker runtime configuration loader."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class WorkerConfig(BaseModel):
    """Configuration settings for tracking-worker."""

    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgres://postgres:postgres@localhost:5432/delivery_db",
        )
    )
    nats_url: str = Field(default_factory=lambda: os.getenv("NATS_URL", "nats://localhost:4222"))
    nats_stream: str = Field(default_factory=lambda: os.getenv("NATS_STREAM", "DELIVERY_EVENTS"))
    nats_subject: str = Field(
        default_factory=lambda: os.getenv("NATS_SUBJECT", "delivery.shipments.created")
    )
    nats_consumer_group: str = Field(
        default_factory=lambda: os.getenv("NATS_CONSUMER_GROUP", "tracking-workers")
    )
    metrics_port: int = Field(default_factory=lambda: int(os.getenv("METRICS_PORT", "9090")))
    health_port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8081")))
    max_retries: int = Field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    retry_backoff_sec: float = Field(
        default_factory=lambda: float(os.getenv("RETRY_BACKOFF_SEC", "1.0"))
    )
    simulation_step_delay_sec: float = Field(
        default_factory=lambda: float(os.getenv("SIMULATION_STEP_DELAY_SEC", "0.2"))
    )


def load_config() -> WorkerConfig:
    """Instantiates and returns the worker config."""
    return WorkerConfig()

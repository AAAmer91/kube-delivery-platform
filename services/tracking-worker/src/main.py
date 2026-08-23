"""Main entrypoint for tracking-worker."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from prometheus_client import start_http_server

from src.config import load_config
from src.consumer import DeliveryEventConsumer
from src.repository import PostgresRepository

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger("tracking-worker.main")

_global_repo: PostgresRepository | None = None
_global_consumer: DeliveryEventConsumer | None = None


def dependencies_ready() -> bool:
    """Returns true only when both stateful dependencies are actively connected."""
    return bool(
        _global_repo is not None
        and _global_repo.is_connected
        and _global_consumer is not None
        and _global_consumer.is_connected
    )


async def connect_database_with_retry(
    repo: PostgresRepository,
    retry_backoff_sec: float,
) -> None:
    """Waits for PostgreSQL during concurrent Kubernetes startup."""
    while True:
        try:
            await repo.connect()
            return
        except Exception as err:
            logger.warning("Database connection failed: %s; retrying", err)
            await asyncio.sleep(retry_backoff_sec)


async def monitor_database(repo: PostgresRepository, retry_backoff_sec: float) -> None:
    """Continuously probes PostgreSQL and rebuilds a failed connection pool."""
    while True:
        if not await repo.ping():
            await repo.close()
            await connect_database_with_retry(repo, retry_backoff_sec)
        await asyncio.sleep(retry_backoff_sec)


class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP probe handler for Kubernetes liveness & readiness."""

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"UP","service":"tracking-worker"}\n')
            return

        if self.path == "/ready":
            is_ready = dependencies_ready()

            if is_ready:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"READY","service":"tracking-worker"}\n')
            else:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"NOT_READY","service":"tracking-worker"}\n')
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        # Suppress standard logging to keep structured JSON logs clean
        pass


def start_health_server(port: int) -> HTTPServer:
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


async def main() -> None:
    """Async main routine."""
    global _global_repo, _global_consumer

    cfg = load_config()
    logger.info("Initializing tracking-worker in environment '%s'...", cfg.environment)

    # Start Prometheus metrics server
    try:
        start_http_server(cfg.metrics_port)
        logger.info("Prometheus metrics server running on port %d", cfg.metrics_port)
    except Exception as err:
        logger.warning("Metrics server start note: %s", err)

    # Start HTTP Health probe server
    health_server = start_health_server(cfg.health_port)
    logger.info("Health probe server running on port %d", cfg.health_port)

    # Initialize repository
    repo = PostgresRepository(cfg.database_url)
    await connect_database_with_retry(repo, cfg.retry_backoff_sec)
    _global_repo = repo

    # Initialize consumer
    consumer = DeliveryEventConsumer(cfg, repo)
    _global_consumer = consumer
    try:
        await consumer.connect()
    except Exception as err:
        logger.warning("NATS initial connect note: %s (will retry in loop)", err)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_signal(sig_name: str) -> None:
        logger.info("Received exit signal '%s', initiating graceful shutdown...", sig_name)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig.name)

    # Run consumer task in background
    consumer_task = asyncio.create_task(consumer.start())
    database_monitor_task = asyncio.create_task(monitor_database(repo, cfg.retry_backoff_sec))

    # Wait for shutdown signal
    await stop_event.wait()

    # Graceful shutdown
    logger.info("Stopping event consumer...")
    await consumer.stop()
    consumer_task.cancel()
    database_monitor_task.cancel()

    logger.info("Closing database connection pool...")
    await repo.close()

    health_server.shutdown()
    logger.info("tracking-worker exited cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)

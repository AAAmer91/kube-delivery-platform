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
            is_ready = True
            if _global_repo is None or _global_consumer is None:
                is_ready = False

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
    try:
        await repo.connect()
        _global_repo = repo
    except Exception as err:
        logger.warning("Database initial connect note: %s (will retry)", err)

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

    # Wait for shutdown signal
    await stop_event.wait()

    # Graceful shutdown
    logger.info("Stopping event consumer...")
    await consumer.stop()
    consumer_task.cancel()

    logger.info("Closing database connection pool...")
    await repo.close()

    health_server.shutdown()
    logger.info("tracking-worker exited cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)

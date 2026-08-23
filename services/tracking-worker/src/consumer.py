"""NATS JetStream consumer and event progression engine."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import nats
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

from src.config import WorkerConfig
from src.metrics import (
    EVENT_PROCESSING_DURATION,
    EVENTS_PROCESSED_TOTAL,
    POISON_MESSAGES_TOTAL,
    WORKER_ACTIVE_TASKS,
)
from src.repository import PostgresRepository

logger = logging.getLogger("tracking-worker.consumer")

STATUS_LIFECYCLE = ["PROCESSING", "IN_TRANSIT", "DELIVERED"]


class DeliveryEventConsumer:
    """Consumes delivery events from NATS JetStream and simulates status progression."""

    def __init__(self, cfg: WorkerConfig, repo: PostgresRepository):
        self._cfg = cfg
        self._repo = repo
        self._nc: Any = None
        self._js: Any = None
        self._psub: Any = None
        self._running = False

    async def connect(self) -> None:
        """Connects to NATS and subscribes to JetStream stream."""
        self._nc = await nats.connect(
            self._cfg.nats_url,
            name="tracking-worker-consumer",
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )
        self._js = self._nc.jetstream()

        # Bind or create durable pull subscriber
        try:
            self._psub = await self._js.pull_subscribe(
                subject=self._cfg.nats_subject,
                durable=self._cfg.nats_consumer_group,
                stream=self._cfg.nats_stream,
                config=ConsumerConfig(
                    durable_name=self._cfg.nats_consumer_group,
                    deliver_policy=DeliverPolicy.ALL,
                    ack_policy=AckPolicy.EXPLICIT,
                    ack_wait=10,
                    max_deliver=self._cfg.max_retries,
                ),
            )
            logger.info(
                "Subscribed to JetStream stream %s with durable group %s",
                self._cfg.nats_stream,
                self._cfg.nats_consumer_group,
            )
        except Exception as err:
            logger.warning("Pull subscribe initialization note: %s", err)

    @property
    def is_connected(self) -> bool:
        """Checks if NATS connection is active."""
        return bool(self._nc is not None and self._nc.is_connected and self._psub is not None)

    async def start(self) -> None:
        """Starts the event consumer processing loop."""
        self._running = True
        logger.info("Starting JetStream event consumption loop...")

        while self._running:
            if not self._psub:
                await asyncio.sleep(1)
                try:
                    await self.connect()
                except Exception as err:
                    logger.debug("Reconnection attempt failed: %s", err)
                continue

            try:
                # Fetch messages in batches of 5 with 1s timeout
                msgs = await self._psub.fetch(batch=5, timeout=1.0)
                for msg in msgs:
                    if not self._running:
                        break
                    await self.process_message(msg)
            except NatsTimeoutError:
                # Normal when queue is idle
                continue
            except Exception as err:
                if self._running:
                    logger.error("Error in consumer fetch loop: %s", err)
                    await asyncio.sleep(0.5)

    async def process_message(self, msg: Any) -> None:
        """Processes a single event with status progression and error handling."""
        start_time = time.perf_counter()
        WORKER_ACTIVE_TASKS.inc()

        try:
            raw_data = msg.data.decode("utf-8")
            try:
                payload = json.loads(raw_data)
            except json.JSONDecodeError as json_err:
                logger.error("Poison message received (Malformed JSON): %s", json_err)
                POISON_MESSAGES_TOTAL.labels(reason="malformed_json").inc()
                await msg.ack()
                return

            shipment_id = payload.get("shipment_id")
            event_type = payload.get("event_type", "Unknown")
            correlation_id = payload.get("correlation_id", "none")

            if not shipment_id:
                logger.error("Poison message received (Missing shipment_id): %s", payload)
                POISON_MESSAGES_TOTAL.labels(reason="missing_shipment_id").inc()
                await msg.ack()
                return

            logger.info(
                "Processing event %s for shipment %s [Correlation: %s]",
                event_type,
                shipment_id,
                correlation_id,
            )

            # Simulate delivery lifecycle progression
            for next_status in STATUS_LIFECYCLE:
                if not self._running:
                    break
                if self._cfg.simulation_step_delay_sec > 0:
                    await asyncio.sleep(self._cfg.simulation_step_delay_sec)

                updated = await self._repo.update_shipment_status(shipment_id, next_status)
                if updated:
                    logger.info(
                        "Shipment %s progressed to %s",
                        shipment_id,
                        next_status,
                    )
                EVENTS_PROCESSED_TOTAL.labels(status=next_status, result="success").inc()

            # Acknowledge message upon complete progression
            await msg.ack()
            duration = time.perf_counter() - start_time
            EVENT_PROCESSING_DURATION.labels(event_type=event_type).observe(duration)

        except Exception as err:
            logger.error("Failed to process event: %s", err)
            EVENTS_PROCESSED_TOTAL.labels(status="FAILED", result="error").inc()
            # Negative acknowledge with backoff for retry
            try:
                await msg.nak(delay=self._cfg.retry_backoff_sec)
            except Exception:
                pass
        finally:
            WORKER_ACTIVE_TASKS.dec()

    async def stop(self) -> None:
        """Gracefully terminates the consumer."""
        self._running = False
        if self._nc is not None:
            await self._nc.drain()
            await self._nc.close()
            logger.info("NATS JetStream consumer stopped cleanly.")

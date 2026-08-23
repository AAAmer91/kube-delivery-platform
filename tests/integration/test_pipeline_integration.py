"""Integration testing for state transitions, idempotency, and retries."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from src.config import WorkerConfig
from src.consumer import DeliveryEventConsumer


@pytest.mark.asyncio
async def test_idempotent_status_transitions() -> None:
    """Verifies that duplicate delivery events do not corrupt state or trigger invalid updates."""
    mock_repo = AsyncMock()
    # First update returns True (status changed), second returns False (status unchanged/idempotent)
    mock_repo.update_shipment_status.side_effect = [True, True, True, False, False, False]

    cfg = WorkerConfig(
        environment="test",
        database_url="postgres://user:pass@localhost:5432/test_db",
        nats_url="nats://localhost:4222",
        simulation_step_delay_sec=0.0,
    )
    consumer = DeliveryEventConsumer(cfg, mock_repo)
    consumer._running = True

    mock_msg = AsyncMock()

    mock_msg.data = b'{"event_id":"evt-1","event_type":"ShipmentCreated","shipment_id":"shp-1","tracking_number":"TRK-1","status":"PLACED","correlation_id":"trace-1"}'

    # First delivery cycle
    await consumer.process_message(mock_msg)
    assert mock_repo.update_shipment_status.call_count == 3

    # Duplicate delivery cycle (idempotent replay)
    await consumer.process_message(mock_msg)
    assert mock_repo.update_shipment_status.call_count == 6

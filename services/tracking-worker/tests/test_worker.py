"""Unit tests for tracking-worker."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import WorkerConfig
from src.consumer import DeliveryEventConsumer


@pytest.fixture
def worker_config() -> WorkerConfig:
    return WorkerConfig(
        environment="test",
        database_url="postgres://user:pass@localhost:5432/test_db",
        nats_url="nats://localhost:4222",
        simulation_step_delay_sec=0.0,
    )


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.update_shipment_status = AsyncMock(return_value=True)
    repo.get_shipment = AsyncMock(return_value={"id": "shp_test1", "status": "DELIVERED"})
    return repo


@pytest.mark.asyncio
async def test_process_valid_shipment_event(
    worker_config: WorkerConfig, mock_repo: AsyncMock
) -> None:
    consumer = DeliveryEventConsumer(worker_config, mock_repo)
    consumer._running = True

    event_payload = {
        "event_id": "evt_12345",
        "event_type": "ShipmentCreated",
        "shipment_id": "shp_test1",
        "tracking_number": "TRK-100-TEST",
        "status": "PLACED",
        "correlation_id": "corr-uuid-123",
    }

    mock_msg = MagicMock()
    mock_msg.data = json.dumps(event_payload).encode("utf-8")
    mock_msg.ack = AsyncMock()
    mock_msg.nak = AsyncMock()

    await consumer.process_message(mock_msg)

    # Verifies all 3 progression states were saved
    assert mock_repo.update_shipment_status.call_count == 3
    mock_repo.update_shipment_status.assert_any_call("shp_test1", "PROCESSING")
    mock_repo.update_shipment_status.assert_any_call("shp_test1", "IN_TRANSIT")
    mock_repo.update_shipment_status.assert_any_call("shp_test1", "DELIVERED")

    # Verifies message acknowledged
    mock_msg.ack.assert_awaited_once()
    mock_msg.nak.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_poison_message_malformed_json(
    worker_config: WorkerConfig, mock_repo: AsyncMock
) -> None:
    consumer = DeliveryEventConsumer(worker_config, mock_repo)

    mock_msg = MagicMock()
    mock_msg.data = b"INVALID_NON_JSON_CORRUPTED_BYTES"
    mock_msg.ack = AsyncMock()

    await consumer.process_message(mock_msg)

    # Poison message should be acknowledged (quarantined) without touching DB
    mock_repo.update_shipment_status.assert_not_awaited()
    mock_msg.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_poison_message_missing_shipment_id(
    worker_config: WorkerConfig, mock_repo: AsyncMock
) -> None:
    consumer = DeliveryEventConsumer(worker_config, mock_repo)

    mock_msg = MagicMock()
    mock_msg.data = json.dumps({"event_type": "ShipmentCreated"}).encode("utf-8")
    mock_msg.ack = AsyncMock()

    await consumer.process_message(mock_msg)

    mock_repo.update_shipment_status.assert_not_awaited()
    mock_msg.ack.assert_awaited_once()

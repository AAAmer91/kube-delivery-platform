"""Contract testing for shipment-api and tracking-worker schemas."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field, ValidationError


class CreateShipmentContract(BaseModel):
    """Schema contract for POST /api/v1/shipments."""

    sender_name: str = Field(min_length=1)
    recipient_name: str = Field(min_length=1)
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    weight_kg: float = Field(gt=0.0)


class ShipmentEventContract(BaseModel):
    """Schema contract for NATS JetStream delivery events."""

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    shipment_id: str = Field(min_length=1)
    tracking_number: str = Field(min_length=1)
    status: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


def test_create_shipment_contract_valid() -> None:
    valid_payload = {
        "sender_name": "Acme Corp",
        "recipient_name": "Jane Doe",
        "origin": "Dallas, TX",
        "destination": "Miami, FL",
        "weight_kg": 15.5,
    }
    model = CreateShipmentContract(**valid_payload)
    assert model.sender_name == "Acme Corp"
    assert model.weight_kg == 15.5


def test_create_shipment_contract_invalid_weight() -> None:
    invalid_payload = {
        "sender_name": "Acme Corp",
        "recipient_name": "Jane Doe",
        "origin": "Dallas, TX",
        "destination": "Miami, FL",
        "weight_kg": -5.0,
    }
    with pytest.raises(ValidationError):
        CreateShipmentContract(**invalid_payload)


def test_shipment_event_contract_valid() -> None:
    valid_event = {
        "event_id": "evt-999",
        "event_type": "ShipmentCreated",
        "shipment_id": "shp-abc-123",
        "tracking_number": "TRK-2026-XYZ",
        "status": "PLACED",
        "correlation_id": "trace-uuid-1",
    }
    event = ShipmentEventContract(**valid_event)
    assert event.event_type == "ShipmentCreated"
    assert event.status == "PLACED"

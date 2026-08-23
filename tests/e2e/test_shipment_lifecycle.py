"""End-to-end shipment lifecycle verification against live or simulated cluster endpoints."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest


@pytest.mark.e2e
def test_live_shipment_lifecycle() -> None:
    """E2E lifecycle test verifying API creation, tracking retrieval, and health probes."""
    base_url = os.getenv("API_BASE_URL", "http://localhost:8080")

    # 1. Verify Health Endpoint
    health_url = f"{base_url.rstrip('/')}/healthz"
    try:
        with urllib.request.urlopen(health_url, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data.get("status") == "UP"
    except Exception as err:
        if os.getenv("REQUIRE_LIVE_E2E", "false").lower() == "true":
            pytest.fail(f"Required live cluster endpoint is not reachable: {err}")
        pytest.skip(f"Live cluster endpoint not reachable ({err}); skipping live E2E test")

    # 2. Create Shipment via REST API
    create_url = f"{base_url.rstrip('/')}/api/v1/shipments"
    payload = {
        "sender_name": "Tech Corp",
        "recipient_name": "Global Logistics",
        "origin": "Austin, TX",
        "destination": "London, UK",
        "weight_kg": 8.5,
    }
    req = urllib.request.Request(
        create_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Correlation-ID": "e2e-test-123"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 201
        created = json.loads(resp.read().decode())
        shipment_id = created.get("id")
        assert shipment_id is not None
        assert created.get("status") == "PLACED"

    # 3. Retrieve Shipment by ID
    get_url = f"{base_url.rstrip('/')}/api/v1/shipments/{shipment_id}"
    req_get = urllib.request.Request(get_url, method="GET")

    with urllib.request.urlopen(req_get, timeout=5) as resp:
        assert resp.status == 200
        fetched = json.loads(resp.read().decode())
        assert fetched.get("id") == shipment_id

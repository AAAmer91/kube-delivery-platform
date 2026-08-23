"""Traffic and Load Generator for Kube Delivery Platform Demo & Progressive Delivery Canary."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import random
import time
import urllib.error
import urllib.request

CITIES = [
    "New York, NY",
    "Los Angeles, CA",
    "Chicago, IL",
    "Austin, TX",
    "Seattle, WA",
    "Miami, FL",
    "Boston, MA",
]
CUSTOMERS = ["Acme Corp", "TechForward", "Global Retail", "Omni Logistics", "BlueSky Inc"]


def generate_mock_shipment() -> dict:
    origin, destination = random.sample(CITIES, 2)
    return {
        "sender_name": random.choice(CUSTOMERS),
        "recipient_name": f"Recipient-{random.randint(100, 999)}",
        "origin": origin,
        "destination": destination,
        "weight_kg": round(random.uniform(0.5, 35.0), 2),
    }


def send_request(url: str, fail_rate: float = 0.0) -> tuple[bool, float]:
    start = time.perf_counter()
    shipment = generate_mock_shipment()

    # Simulate deliberate bad requests for canary failure verification if fail_rate > 0
    if random.random() < fail_rate:
        shipment["weight_kg"] = -1.0  # Triggers 422 error

    data = json.dumps(shipment).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Correlation-ID": f"traffic-gen-{time.time()}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency = (time.perf_counter() - start) * 1000
            return (resp.status in (200, 201), latency)
    except urllib.error.HTTPError:
        latency = (time.perf_counter() - start) * 1000
        return (False, latency)
    except Exception:
        latency = (time.perf_counter() - start) * 1000
        return (False, latency)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo traffic against shipment-api")
    parser.add_argument(
        "--url", default="http://localhost:8080/api/v1/shipments", help="API Target URL"
    )
    parser.add_argument("--count", type=int, default=50, help="Total requests")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent workers")
    parser.add_argument(
        "--fail-rate",
        type=float,
        default=0.0,
        help="Ratio of deliberate error injections (0.0 to 1.0)",
    )
    args = parser.parse_args()

    print(
        f"🚀 Generating {args.count} requests to {args.url} (Concurrency: {args.concurrency}, Error Ratio: {args.fail_rate * 100}%)..."
    )

    start_wall = time.perf_counter()
    success_count = 0
    latencies: list[float] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(send_request, args.url, args.fail_rate) for _ in range(args.count)
        ]
        for future in concurrent.futures.as_completed(futures):
            ok, lat = future.result()
            latencies.append(lat)
            if ok:
                success_count += 1

    total_duration = time.perf_counter() - start_wall
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    throughput = args.count / total_duration if total_duration > 0 else 0.0

    print("\n📊 Traffic Generation Summary:")
    print(f"  • Total Requests: {args.count}")
    print(f"  • Successful:     {success_count} ({success_count / args.count * 100:.1f}%)")
    print(f"  • Throughput:     {throughput:.2f} req/sec")
    print(f"  • Avg Latency:    {avg_latency:.2f} ms")


if __name__ == "__main__":
    main()

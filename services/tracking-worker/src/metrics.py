"""Prometheus metrics for tracking-worker."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# Events processed by status and result
EVENTS_PROCESSED_TOTAL = Counter(
    "kube_delivery_worker_events_processed_total",
    "Total events processed by tracking-worker.",
    ["status", "result"],
)

# Processing duration histogram
EVENT_PROCESSING_DURATION = Histogram(
    "kube_delivery_worker_processing_duration_seconds",
    "Time taken to process an event end-to-end.",
    ["event_type"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Current worker active tasks / consumer lag
WORKER_ACTIVE_TASKS = Gauge(
    "kube_delivery_worker_active_tasks",
    "Number of events currently being processed by worker.",
)

# Poison messages quarantined / sent to DLQ
POISON_MESSAGES_TOTAL = Counter(
    "kube_delivery_worker_poison_messages_total",
    "Total invalid or poison events quarantined.",
    ["reason"],
)

# Database update counter
DATABASE_UPDATES_TOTAL = Counter(
    "kube_delivery_worker_database_updates_total",
    "Total database update operations performed by worker.",
    ["status", "result"],
)

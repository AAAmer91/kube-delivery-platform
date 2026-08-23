package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// HTTPRequestsTotal tracks total requests by path, method, and status code
	HTTPRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "kube_delivery",
			Subsystem: "shipment_api",
			Name:      "http_requests_total",
			Help:      "Total number of HTTP requests processed by shipment-api.",
		},
		[]string{"path", "method", "status"},
	)

	// HTTPRequestDuration tracks latency percentiles (p50, p90, p99)
	HTTPRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Namespace: "kube_delivery",
			Subsystem: "shipment_api",
			Name:      "http_request_duration_seconds",
			Help:      "Duration of HTTP requests in seconds.",
			Buckets:   []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10},
		},
		[]string{"path", "method"},
	)

	// ShipmentsCreatedTotal counts shipments successfully placed
	ShipmentsCreatedTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "kube_delivery",
			Subsystem: "shipment_api",
			Name:      "shipments_created_total",
			Help:      "Total number of shipments created.",
		},
		[]string{"status"},
	)

	// EventsPublishedTotal counts events published to NATS JetStream
	EventsPublishedTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "kube_delivery",
			Subsystem: "shipment_api",
			Name:      "events_published_total",
			Help:      "Total number of delivery events published to NATS JetStream.",
		},
		[]string{"event_type", "status"},
	)

	// DatabaseErrorsTotal tracks database errors
	DatabaseErrorsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "kube_delivery",
			Subsystem: "shipment_api",
			Name:      "database_errors_total",
			Help:      "Total number of database errors encountered.",
		},
		[]string{"operation"},
	)
)

package events

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/config"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/domain"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/metrics"
	"github.com/nats-io/nats.go"
)

type EventPublisher interface {
	PublishShipmentCreated(ctx context.Context, event *domain.ShipmentEvent) error
	Ping(ctx context.Context) error
	Close()
}

type natsConnection interface {
	IsConnected() bool
	RTT() (time.Duration, error)
	Drain() error
	Close()
}

type NatsPublisher struct {
	nc natsConnection
	js nats.JetStreamContext
}

func NewNatsPublisher(cfg *config.Config) (*NatsPublisher, error) {
	opts := []nats.Option{
		nats.Name("shipment-api-publisher"),
		nats.Timeout(5 * time.Second),
		nats.ReconnectWait(2 * time.Second),
		nats.MaxReconnects(-1),
		nats.DisconnectErrHandler(func(nc *nats.Conn, err error) {
			log.Printf("[WARN] NATS disconnected: %v", err)
		}),
		nats.ReconnectHandler(func(nc *nats.Conn) {
			log.Printf("[INFO] NATS reconnected to %s", nc.ConnectedUrl())
		}),
	}

	nc, err := nats.Connect(cfg.NatsURL, opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to NATS: %w", err)
	}

	js, err := nc.JetStream()
	if err != nil {
		nc.Close()
		return nil, fmt.Errorf("failed to obtain JetStream context: %w", err)
	}

	// Ensure stream exists
	streamInfo, err := js.StreamInfo(cfg.NatsStream)
	if streamInfo == nil || err != nil {
		_, err = js.AddStream(&nats.StreamConfig{
			Name:        cfg.NatsStream,
			Description: "Delivery and tracking events stream",
			Subjects:    []string{"delivery.shipments.>"},
			Retention:   nats.LimitsPolicy,
			MaxAge:      24 * time.Hour,
			Storage:     nats.FileStorage,
		})
		if err != nil {
			log.Printf("[INFO] Note on stream creation: %v (might already exist)", err)
		}
	}

	return &NatsPublisher{
		nc: nc,
		js: js,
	}, nil
}

func (p *NatsPublisher) PublishShipmentCreated(ctx context.Context, event *domain.ShipmentEvent) error {
	payload, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal shipment event: %w", err)
	}

	msg := &nats.Msg{
		Subject: "delivery.shipments.created",
		Data:    payload,
		Header:  nats.Header{},
	}
	msg.Header.Set("Nats-Msg-Id", event.EventID)
	msg.Header.Set("X-Correlation-ID", event.CorrelationID)
	msg.Header.Set("Content-Type", "application/json")

	_, err = p.js.PublishMsg(msg)
	if err != nil {
		metrics.EventsPublishedTotal.WithLabelValues("ShipmentCreated", "failed").Inc()
		return fmt.Errorf("failed to publish to JetStream: %w", err)
	}

	metrics.EventsPublishedTotal.WithLabelValues("ShipmentCreated", "success").Inc()
	return nil
}

func (p *NatsPublisher) Ping(ctx context.Context) error {
	if p.nc == nil || !p.nc.IsConnected() {
		return fmt.Errorf("NATS is not connected")
	}
	_, err := p.nc.RTT()
	return err
}

func (p *NatsPublisher) Close() {
	if p.nc != nil {
		p.nc.Drain()
		p.nc.Close()
	}
}

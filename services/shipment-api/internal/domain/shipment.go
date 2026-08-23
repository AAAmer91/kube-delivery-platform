package domain

import (
	"errors"
	"time"
)

type ShipmentStatus string

const (
	StatusPlaced     ShipmentStatus = "PLACED"
	StatusProcessing ShipmentStatus = "PROCESSING"
	StatusInTransit  ShipmentStatus = "IN_TRANSIT"
	StatusDelivered   ShipmentStatus = "DELIVERED"
	StatusCancelled   ShipmentStatus = "CANCELLED"
	StatusFailed      ShipmentStatus = "FAILED"
)

// Shipment represents the core domain model for a delivery package.
type Shipment struct {
	ID             string         `json:"id" db:"id"`
	TrackingNumber string         `json:"tracking_number" db:"tracking_number"`
	SenderName     string         `json:"sender_name" db:"sender_name"`
	RecipientName  string         `json:"recipient_name" db:"recipient_name"`
	Origin         string         `json:"origin" db:"origin"`
	Destination    string         `json:"destination" db:"destination"`
	Status         ShipmentStatus `json:"status" db:"status"`
	WeightKG       float64        `json:"weight_kg" db:"weight_kg"`
	CreatedAt      time.Time      `json:"created_at" db:"created_at"`
	UpdatedAt      time.Time      `json:"updated_at" db:"updated_at"`
}

// CreateShipmentRequest represents the inbound payload to create a new delivery order.
type CreateShipmentRequest struct {
	SenderName    string  `json:"sender_name"`
	RecipientName string  `json:"recipient_name"`
	Origin        string  `json:"origin"`
	Destination   string  `json:"destination"`
	WeightKG      float64 `json:"weight_kg"`
}

func (r *CreateShipmentRequest) Validate() error {
	if r.SenderName == "" {
		return errors.New("sender_name is required")
	}
	if r.RecipientName == "" {
		return errors.New("recipient_name is required")
	}
	if r.Origin == "" {
		return errors.New("origin is required")
	}
	if r.Destination == "" {
		return errors.New("destination is required")
	}
	if r.WeightKG <= 0 {
		return errors.New("weight_kg must be greater than 0")
	}
	return nil
}

// ShipmentEvent represents the CloudEvent-compatible payload published to NATS JetStream.
type ShipmentEvent struct {
	EventID        string         `json:"event_id"`
	EventType      string         `json:"event_type"`
	ShipmentID     string         `json:"shipment_id"`
	TrackingNumber string         `json:"tracking_number"`
	Status         ShipmentStatus `json:"status"`
	Timestamp      time.Time      `json:"timestamp"`
	CorrelationID  string         `json:"correlation_id"`
}

package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/domain"
)

type mockRepository struct {
	shipments map[string]*domain.Shipment
}

func newMockRepository() *mockRepository {
	return &mockRepository{shipments: make(map[string]*domain.Shipment)}
}

func (m *mockRepository) Ping(ctx context.Context) error {
	return nil
}

func (m *mockRepository) Create(ctx context.Context, s *domain.Shipment) error {
	s.CreatedAt = time.Now().UTC()
	s.UpdatedAt = time.Now().UTC()
	m.shipments[s.ID] = s
	m.shipments[s.TrackingNumber] = s
	return nil
}

func (m *mockRepository) GetByID(ctx context.Context, id string) (*domain.Shipment, error) {
	if s, ok := m.shipments[id]; ok {
		return s, nil
	}
	return nil, nil
}

func (m *mockRepository) List(ctx context.Context, limit, offset int) ([]*domain.Shipment, error) {
	var list []*domain.Shipment
	for _, s := range m.shipments {
		list = append(list, s)
	}
	return list, nil
}

func (m *mockRepository) Close() error {
	return nil
}

type mockPublisher struct {
	published []*domain.ShipmentEvent
}

func newMockPublisher() *mockPublisher {
	return &mockPublisher{published: make([]*domain.ShipmentEvent, 0)}
}

func (m *mockPublisher) PublishShipmentCreated(ctx context.Context, event *domain.ShipmentEvent) error {
	m.published = append(m.published, event)
	return nil
}

func (m *mockPublisher) Ping(ctx context.Context) error {
	return nil
}

func (m *mockPublisher) Close() {}

func TestHealthzEndpoint(t *testing.T) {
	server := NewServer(nil, nil, "1.0.0")
	handler := server.Routes()

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var res map[string]any
	if err := json.NewDecoder(w.Body).Decode(&res); err != nil {
		t.Fatalf("failed to decode json: %v", err)
	}
	if res["status"] != "UP" {
		t.Errorf("expected status 'UP', got '%v'", res["status"])
	}
}

func TestReadyEndpoint(t *testing.T) {
	repo := newMockRepository()
	pub := newMockPublisher()
	server := NewServer(repo, pub, "1.0.0")
	handler := server.Routes()

	req := httptest.NewRequest(http.MethodGet, "/ready", nil)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var res map[string]any
	if err := json.NewDecoder(w.Body).Decode(&res); err != nil {
		t.Fatalf("failed to decode json: %v", err)
	}
	if res["status"] != "READY" {
		t.Errorf("expected status 'READY', got '%v'", res["status"])
	}
	if res["database"] != "CONNECTED" {
		t.Errorf("expected database 'CONNECTED', got '%v'", res["database"])
	}
}

func TestReadyEndpointRejectsMissingDependencies(t *testing.T) {
	server := NewServer(nil, nil, "1.0.0")
	req := httptest.NewRequest(http.MethodGet, "/ready", nil)
	w := httptest.NewRecorder()

	server.Routes().ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503, got %d: %s", w.Code, w.Body.String())
	}
}

func TestCreateShipmentHappyPath(t *testing.T) {
	repo := newMockRepository()
	pub := newMockPublisher()
	server := NewServer(repo, pub, "1.0.0")
	handler := server.Routes()

	payload := domain.CreateShipmentRequest{
		SenderName:    "Alice Smith",
		RecipientName: "Bob Jones",
		Origin:        "Seattle, WA",
		Destination:   "New York, NY",
		WeightKG:      4.25,
	}
	body, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/shipments", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected status 201 Created, got %d: %s", w.Code, w.Body.String())
	}

	var res domain.Shipment
	if err := json.NewDecoder(w.Body).Decode(&res); err != nil {
		t.Fatalf("failed to decode created shipment: %v", err)
	}

	if res.ID == "" || res.TrackingNumber == "" {
		t.Errorf("expected generated ID and tracking number, got ID: %s, Tracking: %s", res.ID, res.TrackingNumber)
	}
	if res.Status != domain.StatusPlaced {
		t.Errorf("expected status 'PLACED', got '%s'", res.Status)
	}
	if len(pub.published) != 1 {
		t.Errorf("expected 1 published event, got %d", len(pub.published))
	}
}

func TestCreateShipmentValidationError(t *testing.T) {
	server := NewServer(nil, nil, "1.0.0")
	handler := server.Routes()

	// Missing sender_name and negative weight
	payload := domain.CreateShipmentRequest{
		RecipientName: "Bob Jones",
		Origin:        "Seattle, WA",
		Destination:   "New York, NY",
		WeightKG:      -1.0,
	}
	body, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/shipments", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusUnprocessableEntity {
		t.Fatalf("expected status 422 Unprocessable Entity, got %d", w.Code)
	}
}

func TestCreateShipmentRejectsMissingDependencies(t *testing.T) {
	server := NewServer(nil, nil, "1.0.0")
	payload := domain.CreateShipmentRequest{
		SenderName:    "Alice Smith",
		RecipientName: "Bob Jones",
		Origin:        "Seattle, WA",
		Destination:   "New York, NY",
		WeightKG:      4.25,
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/shipments", bytes.NewReader(body))
	w := httptest.NewRecorder()

	server.Routes().ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503, got %d: %s", w.Code, w.Body.String())
	}
}

package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/domain"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/events"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/metrics"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/repository"
	"github.com/google/uuid"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type Server struct {
	repo      repository.Repository
	publisher events.EventPublisher
	version   string
}

func NewServer(repo repository.Repository, publisher events.EventPublisher, version string) *Server {
	if version == "" {
		version = "1.0.0"
	}
	return &Server{
		repo:      repo,
		publisher: publisher,
		version:   version,
	}
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()

	// Probes & Observability
	mux.HandleFunc("/healthz", s.handleHealthz)
	mux.HandleFunc("/ready", s.handleReady)
	mux.HandleFunc("/version", s.handleVersion)
	mux.Handle("/metrics", promhttp.Handler())

	// Business API v1
	mux.HandleFunc("/api/v1/shipments", s.handleShipments)
	mux.HandleFunc("/api/v1/shipments/", s.handleShipmentByID)

	return s.withMiddleware(mux)
}

func (s *Server) withMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		// Extract or generate Correlation / Trace ID
		correlationID := r.Header.Get("X-Correlation-ID")
		if correlationID == "" {
			correlationID = uuid.New().String()
		}
		w.Header().Set("X-Correlation-ID", correlationID)
		w.Header().Set("Content-Type", "application/json")

		// Response status capture wrapper
		rw := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}

		next.ServeHTTP(rw, r)

		duration := time.Since(start).Seconds()

		// Record RED metrics
		path := normalizePath(r.URL.Path)
		statusStr := strconv.Itoa(rw.statusCode)
		metrics.HTTPRequestsTotal.WithLabelValues(path, r.Method, statusStr).Inc()
		metrics.HTTPRequestDuration.WithLabelValues(path, r.Method).Observe(duration)

		// Structured JSON Access Log
		logJSON(map[string]any{
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
			"method":         r.Method,
			"path":           r.URL.Path,
			"status":         rw.statusCode,
			"duration_ms":    duration * 1000,
			"correlation_id": correlationID,
			"remote_addr":    r.RemoteAddr,
			"user_agent":     r.UserAgent(),
		})
	})
}

func (s *Server) handleHealthz(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"status":    "UP",
		"service":   "shipment-api",
		"timestamp": time.Now().UTC(),
	})
}

func (s *Server) handleReady(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	var dbStatus, natsStatus string
	isReady := true

	if s.repo != nil {
		if err := s.repo.Ping(ctx); err != nil {
			dbStatus = fmt.Sprintf("DOWN: %v", err)
			isReady = false
		} else {
			dbStatus = "CONNECTED"
		}
	} else {
		dbStatus = "DOWN: dependency not initialized"
		isReady = false
	}

	if s.publisher != nil {
		if err := s.publisher.Ping(ctx); err != nil {
			natsStatus = fmt.Sprintf("DOWN: %v", err)
			isReady = false
		} else {
			natsStatus = "CONNECTED"
		}
	} else {
		natsStatus = "DOWN: dependency not initialized"
		isReady = false
	}

	status := http.StatusOK
	statusText := "READY"
	if !isReady {
		status = http.StatusServiceUnavailable
		statusText = "NOT_READY"
	}

	writeJSON(w, status, map[string]any{
		"status":      statusText,
		"service":     "shipment-api",
		"version":     s.version,
		"database":    dbStatus,
		"message_bus": natsStatus,
		"timestamp":   time.Now().UTC(),
	})
}

func (s *Server) handleVersion(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"service": "shipment-api",
		"version": s.version,
	})
}

func (s *Server) handleShipments(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodPost:
		s.createShipment(w, r)
	case http.MethodGet:
		s.listShipments(w, r)
	default:
		writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
	}
}

func (s *Server) createShipment(w http.ResponseWriter, r *http.Request) {
	var req domain.CreateShipmentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Malformed JSON request payload")
		return
	}

	if err := req.Validate(); err != nil {
		writeError(w, http.StatusUnprocessableEntity, err.Error())
		return
	}

	if s.repo == nil || s.publisher == nil {
		writeError(w, http.StatusServiceUnavailable, "Required dependencies are unavailable")
		return
	}

	correlationID := w.Header().Get("X-Correlation-ID")
	shipmentID := fmt.Sprintf("shp_%s", uuid.New().String()[:12])
	trackingNumber := fmt.Sprintf("TRK-%d-%s", time.Now().Unix(), strings.ToUpper(uuid.New().String()[:6]))

	shipment := &domain.Shipment{
		ID:             shipmentID,
		TrackingNumber: trackingNumber,
		SenderName:     req.SenderName,
		RecipientName:  req.RecipientName,
		Origin:         req.Origin,
		Destination:    req.Destination,
		Status:         domain.StatusPlaced,
		WeightKG:       req.WeightKG,
	}

	if err := s.repo.Create(r.Context(), shipment); err != nil {
		log.Printf("[ERROR] Failed to save shipment: %v", err)
		writeError(w, http.StatusInternalServerError, "Failed to persist shipment")
		return
	}

	// Publish event to NATS JetStream
	event := &domain.ShipmentEvent{
		EventID:        uuid.New().String(),
		EventType:      "ShipmentCreated",
		ShipmentID:     shipment.ID,
		TrackingNumber: shipment.TrackingNumber,
		Status:         shipment.Status,
		Timestamp:      time.Now().UTC(),
		CorrelationID:  correlationID,
	}
	if err := s.publisher.PublishShipmentCreated(r.Context(), event); err != nil {
		log.Printf("[ERROR] Failed to publish shipment event: %v", err)
		writeError(w, http.StatusServiceUnavailable, "Failed to publish shipment event")
		return
	}

	metrics.ShipmentsCreatedTotal.WithLabelValues(string(shipment.Status)).Inc()

	writeJSON(w, http.StatusCreated, shipment)
}

func (s *Server) listShipments(w http.ResponseWriter, r *http.Request) {
	limitStr := r.URL.Query().Get("limit")
	offsetStr := r.URL.Query().Get("offset")

	limit, _ := strconv.Atoi(limitStr)
	offset, _ := strconv.Atoi(offsetStr)

	if limit <= 0 {
		limit = 20
	}

	if s.repo == nil {
		writeJSON(w, http.StatusOK, []*domain.Shipment{})
		return
	}

	shipments, err := s.repo.List(r.Context(), limit, offset)
	if err != nil {
		log.Printf("[ERROR] Failed to list shipments: %v", err)
		writeError(w, http.StatusInternalServerError, "Failed to query shipments")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"data":   shipments,
		"count":  len(shipments),
		"limit":  limit,
		"offset": offset,
	})
}

func (s *Server) handleShipmentByID(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/v1/shipments/")
	if id == "" {
		writeError(w, http.StatusBadRequest, "Shipment ID or tracking number required")
		return
	}

	if s.repo == nil {
		writeError(w, http.StatusNotFound, "Shipment not found")
		return
	}

	shipment, err := s.repo.GetByID(r.Context(), id)
	if err != nil {
		log.Printf("[ERROR] Error finding shipment: %v", err)
		writeError(w, http.StatusInternalServerError, "Database error")
		return
	}

	if shipment == nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("Shipment '%s' not found", id))
		return
	}

	writeJSON(w, http.StatusOK, shipment)
}

// Helpers

type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]any{
		"error":     message,
		"status":    status,
		"timestamp": time.Now().UTC(),
	})
}

func logJSON(data map[string]any) {
	bytes, _ := json.Marshal(data)
	log.Println(string(bytes))
}

func normalizePath(path string) string {
	if strings.HasPrefix(path, "/api/v1/shipments/") {
		return "/api/v1/shipments/:id"
	}
	if path == "" {
		return "/"
	}
	return path
}

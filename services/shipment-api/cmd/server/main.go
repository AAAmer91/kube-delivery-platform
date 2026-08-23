package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/config"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/events"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/handlers"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/repository"
)

var Version = "1.0.0"

func retryConnect[T any](
	name string,
	maxAttempts int,
	delay time.Duration,
	connect func() (T, error),
) (T, error) {
	var zero T
	var lastErr error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		value, err := connect()
		if err == nil {
			return value, nil
		}
		lastErr = err
		log.Printf("[WARN] %s connection attempt %d/%d failed: %v", name, attempt, maxAttempts, err)
		if attempt < maxAttempts {
			time.Sleep(delay)
		}
	}
	return zero, fmt.Errorf("%s unavailable after %d attempts: %w", name, maxAttempts, lastErr)
}

func main() {
	log.Printf("[INFO] Starting shipment-api version %s...", Version)

	cfg := config.Load()

	// Initialize PostgreSQL repository
	repo, err := retryConnect("PostgreSQL", 30, 2*time.Second, func() (repository.Repository, error) {
		return repository.NewPostgresRepository(cfg)
	})
	if err != nil {
		log.Fatalf("[FATAL] %v", err)
	}
	defer repo.Close()
	log.Println("[INFO] PostgreSQL repository initialized successfully.")

	// Initialize NATS JetStream publisher
	publisher, err := retryConnect("NATS JetStream", 30, 2*time.Second, func() (events.EventPublisher, error) {
		return events.NewNatsPublisher(cfg)
	})
	if err != nil {
		log.Fatalf("[FATAL] %v", err)
	}
	defer publisher.Close()
	log.Println("[INFO] NATS JetStream publisher initialized successfully.")

	server := handlers.NewServer(repo, publisher, Version)
	httpServer := &http.Server{
		Addr:              fmt.Sprintf(":%s", cfg.Port),
		Handler:           server.Routes(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	// Start server in background goroutine
	go func() {
		log.Printf("[INFO] HTTP Server listening on port %s", cfg.Port)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("[FATAL] HTTP server failed to listen: %v", err)
		}
	}()

	// Listen for SIGTERM / SIGINT for graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	sig := <-quit
	log.Printf("[INFO] Caught signal '%s', initiating graceful shutdown with timeout %v...", sig, cfg.ShutdownTimeout)

	ctx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
	defer cancel()

	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("[ERROR] Server forced to shutdown: %v", err)
	}

	log.Println("[INFO] shipment-api server exited cleanly.")
}

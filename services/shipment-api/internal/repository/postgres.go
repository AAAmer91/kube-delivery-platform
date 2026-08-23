package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/config"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/domain"
	"github.com/AAAmer91/kube-delivery-platform/services/shipment-api/internal/metrics"
	"github.com/jmoiron/sqlx"
	_ "github.com/lib/pq"
)

type Repository interface {
	Ping(ctx context.Context) error
	Create(ctx context.Context, shipment *domain.Shipment) error
	GetByID(ctx context.Context, id string) (*domain.Shipment, error)
	List(ctx context.Context, limit, offset int) ([]*domain.Shipment, error)
	Close() error
}

type PostgresRepository struct {
	db *sqlx.DB
}

func NewPostgresRepository(cfg *config.Config) (*PostgresRepository, error) {
	db, err := sqlx.Connect("postgres", cfg.DatabaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to postgres: %w", err)
	}

	db.SetMaxOpenConns(cfg.DBMaxOpenConns)
	db.SetMaxIdleConns(cfg.DBMaxIdleConns)
	db.SetConnMaxIdleTime(cfg.DBConnMaxIdle)

	repo := &PostgresRepository{db: db}
	if err := repo.initSchema(context.Background()); err != nil {
		return nil, fmt.Errorf("failed to init schema: %w", err)
	}

	return repo, nil
}

func (r *PostgresRepository) initSchema(ctx context.Context) error {
	schema := `
	CREATE TABLE IF NOT EXISTS shipments (
		id VARCHAR(64) PRIMARY KEY,
		tracking_number VARCHAR(64) UNIQUE NOT NULL,
		sender_name VARCHAR(255) NOT NULL,
		recipient_name VARCHAR(255) NOT NULL,
		origin VARCHAR(255) NOT NULL,
		destination VARCHAR(255) NOT NULL,
		status VARCHAR(64) NOT NULL,
		weight_kg NUMERIC(8, 2) NOT NULL,
		created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
		updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
	);

	CREATE INDEX IF NOT EXISTS idx_shipments_tracking_number ON shipments(tracking_number);
	CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status);
	`
	_, err := r.db.ExecContext(ctx, schema)
	return err
}

func (r *PostgresRepository) Ping(ctx context.Context) error {
	return r.db.PingContext(ctx)
}

func (r *PostgresRepository) Create(ctx context.Context, s *domain.Shipment) error {
	query := `
	INSERT INTO shipments (
		id, tracking_number, sender_name, recipient_name, origin, destination, status, weight_kg, created_at, updated_at
	) VALUES (
		$1, $2, $3, $4, $5, $6, $7, $8, $9, $10
	);
	`
	now := time.Now().UTC()
	s.CreatedAt = now
	s.UpdatedAt = now

	_, err := r.db.ExecContext(
		ctx,
		query,
		s.ID,
		s.TrackingNumber,
		s.SenderName,
		s.RecipientName,
		s.Origin,
		s.Destination,
		s.Status,
		s.WeightKG,
		s.CreatedAt,
		s.UpdatedAt,
	)
	if err != nil {
		metrics.DatabaseErrorsTotal.WithLabelValues("create").Inc()
		return fmt.Errorf("failed to insert shipment: %w", err)
	}
	return nil
}

func (r *PostgresRepository) GetByID(ctx context.Context, id string) (*domain.Shipment, error) {
	query := `
	SELECT id, tracking_number, sender_name, recipient_name, origin, destination, status, weight_kg, created_at, updated_at
	FROM shipments
	WHERE id = $1 OR tracking_number = $1
	LIMIT 1;
	`
	var s domain.Shipment
	err := r.db.GetContext(ctx, &s, query, id)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		metrics.DatabaseErrorsTotal.WithLabelValues("get_by_id").Inc()
		return nil, fmt.Errorf("failed to get shipment by id: %w", err)
	}
	return &s, nil
}

func (r *PostgresRepository) List(ctx context.Context, limit, offset int) ([]*domain.Shipment, error) {
	if limit <= 0 || limit > 100 {
		limit = 20
	}
	if offset < 0 {
		offset = 0
	}

	query := `
	SELECT id, tracking_number, sender_name, recipient_name, origin, destination, status, weight_kg, created_at, updated_at
	FROM shipments
	ORDER BY created_at DESC
	LIMIT $1 OFFSET $2;
	`
	var shipments []*domain.Shipment
	err := r.db.SelectContext(ctx, &shipments, query, limit, offset)
	if err != nil {
		metrics.DatabaseErrorsTotal.WithLabelValues("list").Inc()
		return nil, fmt.Errorf("failed to list shipments: %w", err)
	}
	return shipments, nil
}

func (r *PostgresRepository) Close() error {
	return r.db.Close()
}

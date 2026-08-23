package config

import (
	"os"
	"strconv"
	"time"
)

type Config struct {
	Port            string
	DatabaseURL     string
	NatsURL         string
	NatsStream      string
	NatsSubject     string
	Environment     string
	LogLevel        string
	ShutdownTimeout time.Duration
	DBMaxOpenConns  int
	DBMaxIdleConns  int
	DBConnMaxIdle   time.Duration
}

func Load() *Config {
	return &Config{
		Port:            getEnv("PORT", "8080"),
		DatabaseURL:     getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/delivery_db?sslmode=disable"),
		NatsURL:         getEnv("NATS_URL", "nats://localhost:4222"),
		NatsStream:      getEnv("NATS_STREAM", "DELIVERY_EVENTS"),
		NatsSubject:     getEnv("NATS_SUBJECT", "delivery.shipments.created"),
		Environment:     getEnv("ENVIRONMENT", "development"),
		LogLevel:        getEnv("LOG_LEVEL", "info"),
		ShutdownTimeout: getEnvAsDuration("SHUTDOWN_TIMEOUT_SECONDS", 10*time.Second),
		DBMaxOpenConns:  getEnvAsInt("DB_MAX_OPEN_CONNS", 25),
		DBMaxIdleConns:  getEnvAsInt("DB_MAX_IDLE_CONNS", 10),
		DBConnMaxIdle:   getEnvAsDuration("DB_CONN_MAX_IDLE_SECONDS", 5*time.Minute),
	}
}

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func getEnvAsInt(key string, defaultVal int) int {
	if val := os.Getenv(key); val != "" {
		if intVal, err := strconv.Atoi(val); err == nil {
			return intVal
		}
	}
	return defaultVal
}

func getEnvAsDuration(key string, defaultVal time.Duration) time.Duration {
	if val := os.Getenv(key); val != "" {
		if intVal, err := strconv.Atoi(val); err == nil {
			return time.Duration(intVal) * time.Second
		}
	}
	return defaultVal
}

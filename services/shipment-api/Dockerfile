# ==============================================================================
# Build Stage: Multi-stage Go static binary builder with BuildKit cache mounts
# ==============================================================================
FROM --platform=$BUILDPLATFORM golang:1.23-alpine3.20 AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /src

# Leverage Docker cache for module dependencies
COPY go.mod go.sum* ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download -x

# Copy source code
COPY . .

# Build statically linked binary with security flags and stripped debug symbols
ARG VERSION=1.0.0
ARG COMMIT_SHA=unknown
ARG TARGETOS
ARG TARGETARCH
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH:-amd64} \
    go build -trimpath \
    -ldflags="-s -w -X main.Version=${VERSION} -extldflags '-static'" \
    -o /out/shipment-api ./cmd/server

# ==============================================================================
# Runtime Stage: Minimal, unprivileged non-root image (Read-only root compatible)
# ==============================================================================
FROM alpine:3.24.1 AS runtime

# Create dedicated non-root application user and group (UID/GID 10001)
RUN addgroup -g 10001 -S appgroup && \
    adduser -u 10001 -S appuser -G appgroup && \
    apk --no-cache add ca-certificates tzdata curl && \
    mkdir -p /tmp /app && \
    chown -R appuser:appgroup /tmp /app

WORKDIR /app

# Copy CA certs, timezone data, and static binary from builder
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /out/shipment-api /app/shipment-api

# OCI Standard Image Metadata Labels
LABEL org.opencontainers.image.title="shipment-api" \
      org.opencontainers.image.description="Cloud-Native REST API for shipment management and NATS JetStream event publishing" \
      org.opencontainers.image.authors="Ahmed A. Amer" \
      org.opencontainers.image.vendor="Kube Delivery Platform" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/AAAmer91/kube-delivery-platform"

# Enforce non-root execution
USER 10001:10001

# Expose HTTP REST & Prometheus metrics port
EXPOSE 8080

# Container Healthcheck (Readiness endpoint)
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

ENTRYPOINT ["/app/shipment-api"]

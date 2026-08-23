# ==============================================================================
# Build Stage: Compile dependencies in isolated builder container
# ==============================================================================
FROM python:3.14-slim-bookworm AS builder

WORKDIR /build

# Package patch versions intentionally follow the pinned Bookworm base image;
# every build is vulnerability-scanned before publication.
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# BuildKit owns this cache outside the image layer; retaining it accelerates
# dependency downloads without shipping pip's cache in the runtime image.
# hadolint ignore=DL3042
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-warn-script-location --prefix=/install -r requirements.txt

# ==============================================================================
# Runtime Stage: Minimal, unprivileged non-root Python runtime
# ==============================================================================
FROM python:3.14-slim-bookworm AS runtime

# Install minimal runtime shared libraries (libpq)
# Package patch versions intentionally follow the pinned Bookworm base image;
# every build is vulnerability-scanned before publication.
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group (UID/GID 10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/false -M appuser && \
    mkdir -p /tmp /app && \
    chown -R appuser:appgroup /tmp /app

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source code
COPY --chown=appuser:appgroup src/ /app/src/

# OCI Standard Image Metadata Labels
LABEL org.opencontainers.image.title="tracking-worker" \
      org.opencontainers.image.description="Cloud-Native Python event processor consuming delivery events from NATS JetStream" \
      org.opencontainers.image.authors="Ahmed A. Amer" \
      org.opencontainers.image.vendor="Kube Delivery Platform" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/AAAmer91/kube-delivery-platform"

# Enforce non-root execution
USER 10001:10001

# Configure environment for read-only root compatibility and unbuffered stdout
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TMPDIR=/tmp

# Expose HTTP Health Probe and Prometheus metrics ports
EXPOSE 8081 9090

# Container Healthcheck (Readiness endpoint)
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["curl", "--fail", "http://localhost:8081/healthz"]

ENTRYPOINT ["python", "-m", "src.main"]

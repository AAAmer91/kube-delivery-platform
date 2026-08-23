# 🐳 Docker Architecture & Container Hardening Guide

The **Kube Delivery Platform** implements enterprise-grade container engineering designed for zero-trust Kubernetes execution.

---

## 🔒 Security Best Practices Implemented

### 1. Multi-Stage Builds & Minimal Runtime Images
* **`shipment-api` (Go 1.27):**
  - **Stage 1 (Builder):** Uses `golang:1.27.0-alpine3.24` with BuildKit cache mounts (`/go/pkg/mod` and `/root/.cache/go-build`) to compile a statically linked binary with stripped debug symbols (`-ldflags="-s -w -extldflags '-static'"`).
  - **Stage 2 (Runtime):** Uses minimal `alpine:3.24.1` containing only CA certificates, timezone definitions, and the static binary.
* **`tracking-worker` (Python 3.12):**
  - **Stage 1 (Builder):** Compiles wheel dependencies in an isolated Debian build container.
  - **Stage 2 (Runtime):** Uses `python:3.12-slim-bookworm` copying only the installed package prefix.

### 2. Non-Root Execution (UID/GID 10001)
* Neither service runs as `root` (UID 0).
* Dedicated unprivileged user `appuser:appgroup` (UID `10001`, GID `10001`) is created and declared via `USER 10001:10001`.

### 3. Read-Only Root Filesystem Compatibility
* All container runtimes support `readOnlyRootFilesystem: true`.
* Temporary writable scratch space is provided via `tmpfs` mounts at `/tmp`.

### 4. Dropped Linux Capabilities & Seccomp
* Default Linux capabilities are completely dropped (`drop: ["ALL"]`).
* Default runtime seccomp profile is enforced (`seccompProfile: { type: "RuntimeDefault" }`).

### 5. Multi-Architecture Matrix (`linux/amd64`, `linux/arm64`)
* Built using `docker/setup-buildx-action` and QEMU emulation for universal cloud and Apple Silicon compatibility.

---

## 📦 OCI Image Metadata & Supply Chain Security

All container images include OpenContainers Initiative (OCI) standard labels:
```dockerfile
LABEL org.opencontainers.image.title="shipment-api" \
      org.opencontainers.image.description="Cloud-Native REST API for shipment management and NATS JetStream event publishing" \
      org.opencontainers.image.authors="Ahmed A. Amer" \
      org.opencontainers.image.vendor="Kube Delivery Platform" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/AAAmer91/kube-delivery-platform"
```

### Vulnerability Scanning & SBOM Generation
* **Trivy Scanner:** Automated container vulnerability scanning in GitHub Actions with `CRITICAL: 0` blocking gates.
* **CycloneDX SBOM:** Software Bill of Materials generated for full dependency transparency.

# 🚀 Kube Delivery Platform

[![CI/CD Quality Gates](https://github.com/AAAmer91/kube-delivery-platform/actions/workflows/pr-validation.yml/badge.svg)](https://github.com/AAAmer91/kube-delivery-platform/actions/workflows/pr-validation.yml)
[![Kind Runtime & Chaos](https://github.com/AAAmer91/kube-delivery-platform/actions/workflows/e2e-kind.yml/badge.svg)](https://github.com/AAAmer91/kube-delivery-platform/actions/workflows/e2e-kind.yml)
[![Security SAST](https://github.com/AAAmer91/kube-delivery-platform/actions/workflows/security-scans.yml/badge.svg)](https://github.com/AAAmer91/kube-delivery-platform/actions/workflows/security-scans.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An enterprise-grade, cloud-native delivery platform engineered to demonstrate advanced **Docker container hardening**, **Kubernetes platform engineering**, **Argo CD GitOps**, and **Argo Rollouts progressive canary delivery**.

---

## 🏗️ Platform Architecture

```mermaid
flowchart TD
    subgraph ClientLayer ["🌐 Ingress Edge"]
        Client(["HTTP Client / Webhook"])
        Ingress["Ingress NGINX Controller<br/>(Port 80/443 | SSL Termination)"]
    end

    subgraph ClusterMesh ["📦 Kubernetes Cluster (Namespace: delivery)"]
        subgraph Compute ["Compute Workloads"]
            API["shipment-api (Go 1.27)<br/>2 Replicas | HPA (70%) | Non-Root (UID 10001)<br/>Read-Only RootFS | PDB (minAvailable: 1)"]
            Worker["tracking-worker (Python 3.12)<br/>2 Replicas | HPA (75%) | Non-Root (UID 10001)<br/>Async Lifecycle Engine"]
        end

        subgraph EventBus ["Event Streaming Mesh"]
            NATS["NATS JetStream 2.10<br/>Stream: DELIVERY_EVENTS<br/>Subject: delivery.shipments.>"]
        end

        subgraph Persistence ["Stateful Tier"]
            DB[("PostgreSQL 16<br/>StatefulSet + PVC<br/>Pre/Post-Install Migration Job")]
        end

        subgraph Observability ["Telemetry Tier"]
            Prom["Prometheus Server<br/>RED Scrape Targets"]
            Grafana["Grafana Dashboards<br/>Executive KPI View"]
        end
    end

    Client -->|"POST /api/v1/shipments"| Ingress
    Ingress -->|"HTTP Proxy"| API
    API -->|"1. Publish Event"| NATS
    API -->|"Persist Order (PLACED)"| DB
    NATS -->|"2. JetStream Consumer Group"| Worker
    Worker -->|"3. Simulate Progress (DELIVERED)"| DB
    Prom -->|"Scrape /metrics"| API
    Prom -->|"Scrape /metrics"| Worker
    Grafana -->|"Query Metrics"| Prom
```

---

## 🌟 Key Engineering Capabilities

| Engineering Domain | Highlights & Capabilities |
| :--- | :--- |
| **🐳 Docker Engineering** | Multi-stage builds, minimal non-root base images (`UID 10001`), BuildKit cache mounts, read-only root filesystems, explicit health checks, Hadolint linting, blocking Trivy CVE scans, CycloneDX SBOMs, signed provenance/SBOM attestations, and multi-arch images (`linux/amd64`, `linux/arm64`). |
| **☸️ Kubernetes Platform** | Umbrella Helm chart (`values-preview.yaml`, `values-staging.yaml`, `values-prod.yaml`), zero-trust `NetworkPolicy` (default-deny), `HorizontalPodAutoscaler` (HPA), `PodDisruptionBudget` (PDB), `TopologySpreadConstraints`, Pod Anti-Affinity, least-privilege RBAC. |
| **🛡️ Kyverno Governance** | Policy-as-code cluster admission: disallows root users, mandates CPU/memory limits, enforces read-only rootfs, drops ALL capabilities, restricts image registries. |
| **🚀 GitOps & Progressive Delivery** | Argo CD App-of-Apps pattern (`root-app.yaml`, `app-staging.yaml`, `app-prod.yaml`), Argo Rollouts canary traffic steps (`10% -> 25% -> 50% -> 100%`) with automated metric rollback gates (`AnalysisTemplate`). |
| **📊 Observability & RED Metrics** | Prometheus metric scraping, alert rules for error spikes and consumer lag, OpenTelemetry collector, Grafana dashboard as code visualizing RED metrics (Rate, Errors, Duration). |
| **🧪 Automated Chaos Drills** | Automated pod deletion self-healing verification, unauthorized NetworkPolicy breach tests, HPA scaling under load, and deliberate bad-canary rollback drills. |

---

## 📂 Repository Structure

```text
├── services/
│   ├── shipment-api/                  # Go 1.27 REST API Service
│   └── tracking-worker/               # Python 3.12 Event Processor Service
├── deploy/
│   ├── compose/                       # Local Dev Docker Compose & DB Schema
│   ├── helm/kube-delivery-platform/   # Production-Grade Umbrella Helm Chart
│   ├── argocd/                        # Argo CD App-of-Apps & Environment Applications
│   ├── argo-rollouts/                 # Progressive Delivery Rollouts & AnalysisTemplates
│   ├── policies/                      # Kyverno Governance ClusterPolicies
│   └── kind/                          # Multi-Node Kind Cluster Topology
├── observability/
│   ├── prometheus/                    # Alert rules and scrape configs
│   ├── grafana/                       # Dashboards as code (RED Metrics & Pod Health)
│   └── otel/                          # OpenTelemetry collector config
├── tests/
│   ├── contract/                      # OpenAPI & CloudEvent schema tests
│   ├── integration/                   # Idempotency and database tests
│   ├── e2e/                           # End-to-end shipment lifecycle tests
│   └── resilience/                    # Chaos drills (pod recovery, network isolation)
├── scripts/                           # Traffic generation, schema validation, summary tools
├── docs/                              # In-depth architectural documentation
├── Makefile
└── README.md
```

---

## 🚦 Quickstart & Local Verification

### 1. Run Unit & Contract Tests
```bash
make test
```

### 2. Validate Kubernetes & Policy Manifests
```bash
make verify-manifests
```

For Kubernetes deployment, provision a `kube-delivery-database` Secret containing
`POSTGRES_PASSWORD` and `DATABASE_URL`. CI generates an ephemeral Secret; staging
and production are designed for an external secret manager.

### 3. Start Local Docker Compose Stack
```bash
make compose-up
```

---

## 📚 In-Depth Technical Documentation

* [📖 Docker Architecture & Hardening Guide](docs/DOCKER.md)
* [☸️ Kubernetes Platform Architecture](docs/KUBERNETES.md)
* [🚀 GitOps & Progressive Delivery with Argo](docs/GITOPS.md)
* [🛡️ Platform Security & Threat Model](docs/SECURITY.md)
* [📖 Platform Operations & Incident Runbook](docs/RUNBOOK.md)

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).

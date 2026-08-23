# Beginner Guide

This guide explains the project from the outside in. You do not need prior Kubernetes or GitOps experience to follow it.

## What this project models

Imagine a team owns two small services:

- `shipment-api` accepts and returns shipment information.
- `tracking-worker` reacts to shipment events in the background.

The services need a database, a message broker, repeatable packaging, and a controlled way to reach a cluster. This repository brings those pieces together as a proof of concept for an internal delivery platform.

## Follow one shipment

1. A client sends an HTTP request to `shipment-api`.
2. The API validates the request and stores the shipment in PostgreSQL.
3. The API publishes a message to a NATS JetStream subject.
4. `tracking-worker` consumes the message.
5. The worker performs its background processing and updates the stored status.
6. Prometheus-compatible metrics record how the services behave.

This split keeps the user-facing request short while allowing slower work to happen asynchronously.

## The main terms

| Term | Meaning in this repository |
| --- | --- |
| Docker image | A versioned package containing a service and the files it needs to run |
| Container | A running instance of an image |
| Pod | Kubernetes' smallest deployable unit; it wraps one or more containers |
| Deployment | A Kubernetes controller that keeps the requested number of application pods running |
| StatefulSet | A controller for workloads that need stable names or storage, such as PostgreSQL and NATS |
| Service | A stable network address in front of a changing set of pods |
| Helm | A templating and packaging tool for Kubernetes resources |
| GitOps | An operating model in which Git stores the desired cluster configuration and a controller reconciles it |
| Canary | A rollout that sends a small amount of traffic to a new version before increasing exposure |

## Why there are two runtime paths

Docker Compose and Kubernetes serve different purposes here:

- Docker Compose provides a quick local development environment on one machine.
- Kubernetes models scheduling, health checks, scaling, network policy, disruption handling, and controlled rollout across a cluster.

Compose is the fastest way to understand the application. Kubernetes is the path for understanding the platform controls around it.

## How the repository is layered

1. `services/` contains the application behavior.
2. Each service's `Dockerfile` turns that behavior into a container image.
3. `deploy/helm/` describes the shared Kubernetes resources.
4. Environment-specific values live beside the chart in `deploy/helm/kube-delivery-platform/`.
5. `deploy/argocd/` tells Argo CD which configuration to reconcile.
6. `deploy/policies/`, `deploy/argo-rollouts/`, and `observability/` add governance, rollout analysis, and monitoring.
7. `.github/workflows/` verifies and publishes the resulting artifacts.

Each layer answers a different question: what the software does, how it is packaged, how it runs, and how changes are controlled.

## A practical reading path

1. Start the Compose environment using the commands in the [README](../README.md#local-development).
2. Read [Docker design](DOCKER.md) to see how the service images are built.
3. Read [Kubernetes deployment](KUBERNETES.md) to understand the workloads and runtime controls.
4. Read [GitOps and rollout model](GITOPS.md) to see how desired state reaches a cluster.
5. Finish with the [security model](SECURITY.md) and [operations runbook](RUNBOOK.md).

## Proof-of-concept boundaries

The repository provides a working baseline for evaluating the approach, not a complete company platform. A production implementation would normally replace in-cluster stateful dependencies with managed or carefully operated services, integrate an external secret manager and organization identity provider, define backup and disaster-recovery objectives, and size the platform from measured demand.

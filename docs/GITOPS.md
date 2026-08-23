# GitOps and Progressive Delivery

This proof of concept uses Git as the reviewed record of desired cluster state. Argo CD compares that state with the cluster and applies the configured reconciliation policy. Operational access still needs a documented break-glass procedure for incidents in a production implementation.

## Reconciliation model

```mermaid
graph TD
    Root[Root application] --> Controllers[Ingress, Argo Rollouts, and Kyverno]
    Root --> Observe[Prometheus and Grafana]
    Root --> Govern[Kyverno policies]
    Root --> Staging[Staging application]
    Root --> Production[Production application]
```

Argo CD is the bootstrap prerequisite. Applying `deploy/argocd/root-app.yaml` creates the app-of-apps hierarchy. Sync waves place controllers before the resources that depend on them:

- platform controllers use sync wave `-4`;
- observability uses `-2`;
- governance uses `-1`;
- application environments follow those dependencies.

The staging application enables automated sync and pruning. Production sync is manual so that repository environment protection and an operator approval can control promotion.

## Canary rollout

For staging and production, Helm renders `shipment-api` as an Argo Rollout. NGINX canary ingress resources route traffic between stable and candidate ReplicaSets.

The configured sequence is:

1. route 10% of traffic to the candidate, pause, and analyze;
2. route 25%, pause, and analyze;
3. route 50%, pause, and analyze;
4. route 100% and complete the promotion.

At each analysis step, Prometheus queries check that:

- the HTTP 5xx ratio is at most 1%;
- p99 request latency is at most 500 ms.

Three failed measurements cause the rollout to abort. Argo Rollouts then returns traffic to the stable ReplicaSet. Availability still depends on ingress health, capacity, application compatibility, and the metrics pipeline, so the mechanism should be tested under the conditions of the target cluster.

## Image promotion

Application images are referenced by immutable digest in environment values. The promotion workflow updates those values through a pull request, which keeps the proposed artifact change reviewable and auditable.

## Operator commands

Set the namespace and release-specific rollout name before using these commands:

```bash
kubectl argo rollouts get rollout kube-delivery-shipment-api -n delivery
kubectl argo rollouts promote kube-delivery-shipment-api -n delivery
kubectl argo rollouts abort kube-delivery-shipment-api -n delivery
kubectl argo rollouts undo kube-delivery-shipment-api -n delivery
```

Use `promote` only after reviewing the current analysis results. `abort` stops the active update; `undo` changes the desired revision and should be reconciled with Git afterward.

## Limitations

The repository defines the applications and rollout policy but does not provision a shared Argo CD control plane, DNS, certificates, or a managed Prometheus service. Those are platform-level concerns for the target environment.

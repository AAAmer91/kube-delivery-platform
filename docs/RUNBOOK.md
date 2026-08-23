# Operations Runbook

This runbook covers initial diagnosis for the failure modes exercised by the proof of concept. Replace the example namespace and resource names if the Helm release uses different values, and follow the target environment's incident and change procedures.

Set reusable values first:

```bash
export NAMESPACE=delivery
export RELEASE=kube-delivery
```

## High API error rate

Expected signals include the `HighHttpErrorRate` alert, a rising HTTP 5xx ratio, or failed API readiness checks.

### Diagnose

```bash
kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=shipment-api --tail=100
kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=postgres
kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=nats
kubectl describe pods -n "$NAMESPACE" -l app.kubernetes.io/name=shipment-api
kubectl argo rollouts get rollout "$RELEASE-shipment-api" -n "$NAMESPACE"
```

Correlate the first error with deployments, database saturation, NATS availability, and node events before changing the workload.

### Recover

- If an active candidate introduced the errors, abort it and restore the previous revision:

  ```bash
  kubectl argo rollouts abort "$RELEASE-shipment-api" -n "$NAMESPACE"
  kubectl argo rollouts undo "$RELEASE-shipment-api" -n "$NAMESPACE"
  ```

- If dependency capacity is exhausted, reduce incoming load or scale the affected dependency according to its data-safety procedure. Restarting application pods may clear a transient connection failure but should follow evidence that it addresses the cause.

After recovery, confirm readiness, error rate, and latency, then reconcile any emergency revision change back into Git.

## Worker backlog or poison events

Expected signals include `ExcessiveWorkerPoisonEvents`, increasing delivery lag, repeated message processing errors, or worker readiness failures.

### Diagnose

```bash
kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=tracking-worker --tail=100
kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=tracking-worker
kubectl describe pods -n "$NAMESPACE" -l app.kubernetes.io/name=tracking-worker
kubectl port-forward -n "$NAMESPACE" service/"$RELEASE-nats" 8222:8222
```

While the port-forward is active, inspect the NATS monitoring endpoint from another terminal:

```bash
curl --fail --silent http://127.0.0.1:8222/jsz?streams=true\&consumers=true
```

Check whether failures are transient, message-specific, database-related, or caused by insufficient consumer capacity.

### Recover

- For a healthy but undersized worker, change the replica target through the environment values and GitOps promotion path.
- For an immediate incident response, a temporary scale operation can be used if the environment procedure allows it:

  ```bash
  kubectl scale deployment/"$RELEASE-tracking-worker" -n "$NAMESPACE" --replicas=6
  ```

- Quarantine or replay poison messages only after identifying why processing is not idempotent or retry-safe.

Record temporary cluster changes in Git or revert them after the incident so Argo CD does not silently replace the intended recovery action.

## Closeout

For either incident, capture the timeline, user impact, triggering change, recovery action, and follow-up owner. Verify that alerts returned to normal and that the declared Git state matches the cluster.

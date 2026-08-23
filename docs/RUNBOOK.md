# 📖 Platform Operations Runbook & Incident Response

This operational runbook provides diagnostic commands, recovery procedures, and chaos remediation drills.

---

## 🚨 Incident 1: High HTTP 5xx Error Rate on `shipment-api`

### Symptoms
* Prometheus Alert: `HighHttpErrorRate` firing ($> 5\%$).
* Grafana RED Dashboard displays red status on `HTTP Error Rate`.

### Diagnostic Steps
```bash
# Check shipment-api logs for errors
kubectl logs -n delivery -l app.kubernetes.io/name=shipment-api --tail=100 -f

# Verify database and NATS readiness
kubectl get pods -n delivery -l app.kubernetes.io/name=postgres
kubectl get pods -n delivery -l app.kubernetes.io/name=nats

# Check endpoint readiness probe details
kubectl describe pod -n delivery -l app.kubernetes.io/name=shipment-api
```

### Remediation
1. If database connection pool is saturated, scale database resources or restart API pods:
   ```bash
   kubectl rollout restart deployment/kube-delivery-shipment-api -n delivery
   ```
2. If caused by a bad rollout, trigger immediate rollback:
   ```bash
   kubectl argo rollouts abort kube-delivery-shipment-api -n delivery
   kubectl argo rollouts undo kube-delivery-shipment-api -n delivery
   ```

---

## 🚨 Incident 2: High NATS JetStream Consumer Lag / Worker Failure

### Symptoms
* Prometheus Alert: `ExcessiveWorkerPoisonEvents`.
* Worker active tasks metric spiking.

### Diagnostic Steps
```bash
# Check tracking-worker logs
kubectl logs -n delivery -l app.kubernetes.io/name=tracking-worker --tail=100 -f

# Inspect NATS JetStream stream statistics
kubectl exec -it -n delivery statefulset/kube-delivery-nats -- nats stream info DELIVERY_EVENTS
```

### Remediation
1. Scale up worker replicas:
   ```bash
   kubectl scale deployment/kube-delivery-tracking-worker -n delivery --replicas=6
   ```
2. Check database write performance and restart worker pods if deadlock occurs.

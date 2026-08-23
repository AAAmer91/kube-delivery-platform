# 🛡️ Platform Security & Threat Modeling

The **Kube Delivery Platform** implements defense-in-depth security across the container runtime, cluster admission, network mesh, and CI/CD supply chain.

---

## 🔒 Defense-in-Depth Matrix

| Layer | Threat Vector | Mitigation Strategy | Implemented Mechanism |
| :--- | :--- | :--- | :--- |
| **Supply Chain** | Compromised dependencies or malicious base images | Immutable application digests, automated SAST/SBOM, Trivy scanning | `trivy-action`, Hadolint, pinned action SHAs |
| **Container Runtime** | Privilege escalation & container escape | Non-root users, dropped capabilities, read-only rootfs | `USER 10001:10001`, `drop: ["ALL"]`, `seccompProfile: RuntimeDefault` |
| **Cluster Admission** | Rogue or insecure workload deployments | Policy-as-code admission control | Kyverno ClusterPolicies (`deploy/policies/`) |
| **Network Mesh** | Lateral movement after container compromise | Zero-trust microsegmentation | Kubernetes `NetworkPolicy` (default-deny all ingress/egress) |
| **Service Accounts** | Token theft via stolen service account tokens | Token disabling for unprivileged pods | `automountServiceAccountToken: false` |

---

## 📋 Kyverno Governance Enforcement

The following policies are enforced in namespaces labeled
`platform.kube-delivery.io/security-profile=restricted`:
1. **`disallow-root-user`:** Blocks any pod where `runAsNonRoot != true` or `runAsUser == 0`.
2. **`require-resource-limits`:** Blocks any workload without explicit CPU/memory requests and limits.
3. **`require-read-only-rootfs`:** Enforces `readOnlyRootFilesystem: true` for application workloads; the PostgreSQL data workload is explicitly exempted and constrained by the remaining controls.
4. **`require-drop-all-capabilities`:** Enforces `capabilities: { drop: ["ALL"] }`.
5. **`restrict-image-registries`:** Only allows pulls from approved container registries (`ghcr.io`, `docker.io`, `gcr.io`, `quay.io`).

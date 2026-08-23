# Security Model

This document records the threat assumptions and controls included in the proof of concept. It is a starting point for review, not a certification or a substitute for a threat model tied to a specific organization and cluster.

## Trust boundaries

The main boundaries are the source repository and workflow runner, the container registry, Kubernetes admission, the application namespace, and the data services. The model assumes GitHub-hosted workflow identity, a correctly configured cluster, and administrators who protect repository and cluster access.

## Layered controls

| Layer | Example risk | Current control |
| --- | --- | --- |
| Source and build | Modified dependencies, actions, or base images | Pinned action references, CodeQL, dependency review, Hadolint, and Trivy |
| Artifact | An image cannot be traced to its source | Immutable digests, SBOMs, provenance, and keyless signatures |
| Admission | A workload requests unsafe privileges | Kyverno validation policies |
| Container | Privilege escalation or writable system paths | Non-root identity, dropped capabilities, read-only root filesystem, and seccomp |
| Network | Unnecessary lateral access after compromise | Default-deny network policy with explicit service paths |
| Kubernetes API | Application token theft | Dedicated service accounts with token automount disabled |

## Admission rules

Namespaces labeled `platform.kube-delivery.io/security-profile=restricted` are subject to policies that:

1. require non-root execution;
2. require CPU and memory requests and limits;
3. require a read-only root filesystem for application workloads;
4. require all Linux capabilities to be dropped;
5. restrict images to the configured registry allowlist.

PostgreSQL has a documented filesystem exception because its data directory must be writable. Other controls continue to apply, and exceptions should not be generalized to unrelated workloads.

## Residual risks and production work

The repository does not configure an external secret manager, workload identity provider, encrypted backup policy, certificate lifecycle, runtime detection system, or organization-wide audit retention. Registry allowlisting also does not establish that every image in an allowed registry is trusted; digest policy and signature verification should be added for a production control plane.

Base images, Go modules, Python packages, Helm dependencies, and workflow actions require ongoing update ownership. Scan results should be triaged in context rather than treated as proof that an image is safe.

## Vulnerability reporting

Use the process in the repository-level [security policy](../SECURITY.md) to report a suspected vulnerability privately.

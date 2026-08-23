# Docker Design

Docker provides the packaging boundary for the two application services. The image definitions aim to keep build tooling out of runtime images and to support the restricted security context used by the Helm chart.

## Image construction

### `shipment-api`

The Go service uses a multi-stage build:

1. `golang:1.27.0-alpine3.24` downloads modules and compiles a statically linked binary. BuildKit cache mounts retain the module and compiler caches between builds.
2. `alpine:3.24.1` supplies CA certificates, timezone data, and the compiled binary for runtime.

The linker flags strip debug symbols and remove the dependency on a runtime C library. This reduces the image contents, although debugging production binaries may require retaining symbols in a separate artifact.

### `tracking-worker`

The Python service builds dependencies in a Debian-based builder and copies the installed package prefix into `python:3.12-slim-bookworm`. Compilers and package build tools therefore do not remain in the final image.

## Runtime identity and filesystem

Both images declare the unprivileged identity `10001:10001`. The Kubernetes configuration also enforces:

- `runAsNonRoot: true`
- `readOnlyRootFilesystem: true`
- all Linux capabilities dropped
- the runtime-default seccomp profile

Temporary files are written to an explicit `/tmp` volume. These controls need enforcement at deployment time; a Dockerfile declaration alone cannot prevent an operator from overriding them.

## Build targets and metadata

The image workflow uses Docker Buildx and QEMU to produce `linux/amd64` and `linux/arm64` images. OCI labels record the source repository, license, revision, and image description so a published artifact can be traced back to its build.

## Supply-chain outputs

The GitHub workflows:

- scan images with Trivy and fail on configured critical findings;
- generate a CycloneDX software bill of materials (SBOM);
- attach GitHub build provenance;
- sign published image digests with keyless Cosign signing.

After those controls complete, each matrix job writes an image-coordinate table to the GitHub Actions run summary. It distinguishes the source commit from the OCI manifest digest, shows the immutable `repository@sha256:...` reference, and provides the exact input name expected by the GitOps promotion workflow.

These outputs improve traceability but do not replace dependency review, base-image maintenance, or runtime monitoring.

## Local inspection

Build the services through Compose:

```bash
docker compose -f deploy/compose/docker-compose.yml build
```

Inspect the configured runtime user and labels:

```bash
docker image inspect kube-delivery-platform-shipment-api \
  --format '{{json .Config.User}} {{json .Config.Labels}}'
```

Image names can differ when a Compose project name is supplied. The CI image workflow is the authoritative path for multi-architecture publishing and attestations.

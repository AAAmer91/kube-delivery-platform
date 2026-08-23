# GitHub Repository Setup

The workflows are committed as code, but the controls below must be enabled once in GitHub.

## Actions permissions

In **Settings → Actions → General**:

- Allow the actions used by this repository.
- Keep the default `GITHUB_TOKEN` restricted; each workflow declares its own least-privilege permissions.
- Enable **Allow GitHub Actions to create and approve pull requests** so digest promotions can open PRs.

No long-lived cloud or registry credential is required. GHCR publishing and GitHub attestations use the
short-lived repository `GITHUB_TOKEN` and GitHub OIDC.

## Ruleset for `main`

Create a repository ruleset targeting `main` and require pull requests plus these status checks:

- `Unit Tests & Lint / shipment-api (Go)`
- `Unit Tests & Lint / tracking-worker (Python)`
- `Dockerfile Lint & Security (Hadolint)`
- `Helm Chart Lint & Template Validation`
- `Kind Kubernetes Runtime & Chaos Drills`
- `CodeQL Analysis (Go & Python) (go)`
- `CodeQL Analysis (Go & Python) (python)`

Also require conversation resolution, block force pushes/deletions, and require the branch to be current
before merge.

## Protected environments

Create `staging` and `production` in **Settings → Environments**. Add required reviewers and a deployment
branch rule for `production`; optionally add a wait timer. The GitOps promotion workflow binds its job to
the selected environment, so production cannot start until those controls approve it.

## OpenSSF Scorecard

Scorecard runs on pushes to `main`, every Saturday, and manual dispatch. Publishing the public badge is
free for public repositories. Private repositories require GitHub Advanced Security; without it, keep the
repository private and run the Scorecard CLI outside GitHub instead.

## GHCR packages

After the first successful image workflow, make `shipment-api` and `tracking-worker` packages public if
the Kubernetes target must pull without an `imagePullSecret`. Keep package inheritance linked to this
repository so the workflow retains write access.

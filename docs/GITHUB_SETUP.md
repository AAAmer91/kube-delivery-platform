# GitHub Repository Setup

The workflow files define repository automation, while several enforcement controls live in GitHub settings. Configure the items below before treating workflow results as release gates.

## Actions permissions

In **Settings → Actions → General**:

- Allow the actions used by this repository.
- Keep the default `GITHUB_TOKEN` restricted; each workflow declares its own least-privilege permissions.
- Enable **Allow GitHub Actions to create and approve pull requests** so digest promotions can open PRs.

No long-lived cloud or registry credential is required. GHCR publishing and GitHub attestations use the
short-lived repository `GITHUB_TOKEN` and GitHub OIDC.

## Ruleset for `main`

Create a repository ruleset targeting `main` and require pull requests plus the status checks that match the workflow job names:

- `Unit Tests & Lint / shipment-api (Go)`
- `Unit Tests & Lint / tracking-worker (Python)`
- `Dockerfile Lint & Security (Hadolint)`
- `Helm Chart Lint & Template Validation`
- `Kind Kubernetes Runtime & Chaos Drills`
- `CodeQL Analysis (Go & Python) (go)`
- `CodeQL Analysis (Go & Python) (python)`

Also require conversation resolution, block force pushes and branch deletion, and require the branch to be current before merge. Recheck the ruleset when workflow job names change; GitHub does not automatically update required-check names.

## Protected environments

Create `staging` and `production` in **Settings → Environments**. Add required reviewers and a deployment branch rule for `production`; optionally add a wait timer. The GitOps promotion workflow binds its job to the selected environment, so GitHub applies those controls before the job starts.

## OpenSSF Scorecard

Scorecard runs on pushes to `main`, every Saturday, and manual dispatch. Publishing the public badge is free for public repositories. Private repositories require GitHub Advanced Security for the integrated result; without it, run the Scorecard CLI in a separate approved environment. A skipped Scorecard job is expected on unsupported event types when its job-level condition is not met.

The workflow preserves the restricted OpenSSF publishing job and renders its SARIF artifact in a separate, read-only summary job. The run summary reports entries by check and links to the canonical OpenSSF report and GitHub Code Scanning; it does not infer an aggregate score from SARIF.

## GHCR packages

After the first successful image workflow, choose package visibility based on the target cluster. Public packages can be pulled without credentials; private packages require an `imagePullSecret` or workload-specific registry identity. Keep package inheritance linked to this repository so the workflow retains write access.

## Verification

After configuration, open a pull request and confirm that required checks appear, image publishing is skipped for untrusted pull-request code, and production promotion waits for the configured environment approval. Repository settings should be reviewed periodically because they are not versioned with the workflow files.

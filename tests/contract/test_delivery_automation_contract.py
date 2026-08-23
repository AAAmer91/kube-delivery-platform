from __future__ import annotations

from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _workflow(name: str) -> dict[str, object]:
    path = REPOSITORY_ROOT / ".github" / "workflows" / name
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_successful_main_build_promotes_its_exact_digest_pair_to_staging() -> None:
    build = _workflow("build-and-publish.yml")
    push = build["on"]["push"]
    jobs = build["jobs"]

    assert push["branches"] == ["main"]
    assert push["paths"] == ["services/**", ".github/workflows/build-and-publish.yml"]

    build_steps = jobs["build-and-scan"]["steps"]
    coordinate_step = next(
        step for step in build_steps if step["name"] == "Publish immutable image coordinates"
    )
    assert (
        'printf \'%s\\n\' "${DIGEST}" > "image-digests/${SERVICE_NAME}.digest"'
        in coordinate_step["run"]
    )
    digest_artifact = next(
        step for step in build_steps if step["name"] == "Upload immutable image digest"
    )
    assert digest_artifact["with"] == {
        "name": "image-digest-${{ matrix.service.name }}",
        "path": "image-digests/${{ matrix.service.name }}.digest",
        "if-no-files-found": "error",
        "retention-days": "7",
    }

    collector = jobs["collect-image-digests"]
    assert collector["needs"] == "build-and-scan"
    assert collector["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert collector["outputs"] == {
        "shipment_api_digest": "${{ steps.collect.outputs.shipment_api_digest }}",
        "tracking_worker_digest": "${{ steps.collect.outputs.tracking_worker_digest }}",
    }
    assert any(
        "python scripts/collect_image_digests.py" in step.get("run", "")
        for step in collector["steps"]
    )

    promotion = jobs["promote-staging"]
    assert promotion["needs"] == "collect-image-digests"
    assert promotion["uses"] == "./.github/workflows/gitops-deploy.yml"
    assert promotion["with"] == {
        "environment": "staging",
        "shipment_api_digest": "${{ needs.collect-image-digests.outputs.shipment_api_digest }}",
        "tracking_worker_digest": "${{ needs.collect-image-digests.outputs.tracking_worker_digest }}",
    }


def test_gitops_workflow_remains_manual_and_accepts_typed_reusable_inputs() -> None:
    gitops = _workflow("gitops-deploy.yml")
    triggers = gitops["on"]

    assert "workflow_dispatch" in triggers
    assert triggers["workflow_call"]["inputs"] == {
        "environment": {
            "description": "Target deployment environment",
            "required": "true",
            "type": "string",
        },
        "shipment_api_digest": {
            "description": "shipment-api digest (sha256:...)",
            "required": "true",
            "type": "string",
        },
        "tracking_worker_digest": {
            "description": "tracking-worker digest (sha256:...)",
            "required": "true",
            "type": "string",
        },
    }


def test_bot_created_promotion_pr_dispatches_every_required_validation_workflow() -> None:
    gitops = _workflow("gitops-deploy.yml")
    security = _workflow("security-scans.yml")

    assert gitops["permissions"]["actions"] == "write"
    dispatch_step = next(
        step
        for step in gitops["jobs"]["promote-gitops-state"]["steps"]
        if step["name"] == "Dispatch required promotion checks"
    )
    assert dispatch_step["if"] == "steps.promotion.outputs.changed == 'true'"
    for workflow in ("pr-validation.yml", "e2e-kind.yml", "security-scans.yml"):
        assert f'gh workflow run "{workflow}" --ref "${{PROMOTION_BRANCH}}"' in dispatch_step["run"]

    assert "workflow_dispatch" in security["on"]


def test_python_quality_gate_reports_unit_contract_and_integration_failures_separately() -> None:
    validation = _workflow("pr-validation.yml")
    steps = validation["jobs"]["test-tracking-worker"]["steps"]
    commands = {step["name"]: step.get("run", "") for step in steps}

    assert "services/tracking-worker/tests" in commands["Run Python Unit Tests with Coverage"]
    assert "--cov=services/tracking-worker/src" in commands["Run Python Unit Tests with Coverage"]
    assert "tests/contract" in commands["Run Contract Tests"]
    assert "tests/integration" in commands["Run Integration Tests"]

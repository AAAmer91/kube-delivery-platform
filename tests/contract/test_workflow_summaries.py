from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.render_scorecard_summary import load_sarif, render_summary

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _scorecard_sarif() -> dict[str, object]:
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Scorecard",
                        "semanticVersion": "5.2.1",
                        "rules": [
                            {
                                "id": "PinnedDependenciesID",
                                "name": "Pinned-Dependencies",
                                "helpUri": "https://example.test/pinned-dependencies",
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "PinnedDependenciesID",
                        "level": "warning",
                        "message": {"text": "Score is 7 out of 10."},
                    }
                ],
            },
            {
                "tool": {
                    "driver": {
                        "name": "Scorecard",
                        "semanticVersion": "5.2.1",
                        "rules": [
                            {
                                "id": "DangerousWorkflowID",
                                "name": "Dangerous-Workflow",
                                "helpUri": "https://example.test/dangerous-workflow",
                            }
                        ],
                    }
                },
                "results": [],
            },
        ],
    }


def test_render_summary_reports_sarif_entries_without_inventing_an_overall_score() -> None:
    summary = render_summary(
        _scorecard_sarif(),
        repository="AAAmer91/kube-delivery-platform",
        commit_sha="0123456789abcdef",
        run_url="https://github.example/actions/runs/42",
    )

    assert "# OpenSSF Scorecard" in summary
    assert "`0123456789ab`" in summary
    assert "| Checks represented | 2 |" in summary
    assert "| Warning entries | 1 |" in summary
    assert (
        "| [Pinned-Dependencies](https://example.test/pinned-dependencies) | 0 | 1 | 0 | 1 |"
        in summary
    )
    assert (
        "| [Dangerous-Workflow](https://example.test/dangerous-workflow) | 0 | 0 | 0 | 0 |"
        in summary
    )
    assert "[OpenSSF report]" in summary
    assert "[Code scanning]" in summary
    assert "[Workflow run](https://github.example/actions/runs/42)" in summary
    assert "overall score" not in summary.lower()


def test_load_sarif_rejects_an_empty_scan_instead_of_reporting_success(tmp_path: Path) -> None:
    result_path = tmp_path / "results.sarif"
    result_path.write_text(json.dumps({"version": "2.1.0", "runs": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="no runs"):
        load_sarif(result_path)


def test_workflows_publish_human_readable_coordinates_without_weakening_scorecard_job() -> None:
    scorecard = (REPOSITORY_ROOT / ".github/workflows/scorecard.yml").read_text(encoding="utf-8")
    build = (REPOSITORY_ROOT / ".github/workflows/build-and-publish.yml").read_text(
        encoding="utf-8"
    )

    analysis_job = scorecard.split("  summary:", maxsplit=1)[0]
    approved_scorecard_actions = {
        "actions/checkout",
        "actions/upload-artifact",
        "github/codeql-action/upload-sarif",
        "ossf/scorecard-action",
        "step-security/harden-runner",
    }
    analysis_actions = {
        match.split("@", maxsplit=1)[0]
        for match in re.findall(r"^\s+uses:\s+([^\s]+)", analysis_job, flags=re.MULTILINE)
    }

    assert "render_scorecard_summary.py" not in analysis_job
    assert "        run:" not in analysis_job
    assert analysis_actions <= approved_scorecard_actions
    assert "  summary:" in scorecard
    assert "needs: analysis" in scorecard
    assert "actions/download-artifact@" in scorecard
    assert "python scripts/render_scorecard_summary.py" in scorecard

    assert "Publish immutable image coordinates" in build
    assert "DIGEST: ${{ steps.build.outputs.digest }}" in build
    assert "digest_pattern='^sha256:[a-f0-9]{64}$'" in build
    assert "GITHUB_STEP_SUMMARY" in build
    assert "GitOps promotion input" in build
    assert build.index("Upload SBOM evidence") < build.index("Publish immutable image coordinates")

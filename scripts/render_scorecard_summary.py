"""Render OpenSSF Scorecard SARIF as a human-readable GitHub job summary."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

SarifPayload = dict[str, Any]


@dataclass
class CheckSummary:
    """Counts associated with one Scorecard check in SARIF."""

    error: int = 0
    warning: int = 0
    note: int = 0
    other: int = 0
    help_uri: str | None = None

    def add(self, level: str) -> None:
        bucket = level if level in {"error", "warning", "note"} else "other"
        setattr(self, bucket, getattr(self, bucket) + 1)

    @property
    def entries(self) -> int:
        return self.error + self.warning + self.note + self.other


def load_sarif(path: Path) -> SarifPayload:
    """Load a non-empty SARIF 2.1.0 Scorecard result."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read Scorecard SARIF: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("version") != "2.1.0":
        raise ValueError("Scorecard result is not SARIF 2.1.0")

    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("Scorecard SARIF contains no runs")

    return payload


def _markdown_text(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _safe_http_url(value: object) -> str | None:
    url = str(value)
    return url if url.startswith(("https://", "http://")) else None


def _rule_name(rule: dict[str, Any]) -> str:
    return _markdown_text(rule.get("name") or rule.get("id") or "Unknown check")


def _collect_checks(
    runs: list[Any],
) -> tuple[dict[str, CheckSummary], Counter[str], set[str]]:
    checks: dict[str, CheckSummary] = {}
    totals: Counter[str] = Counter()
    versions: set[str] = set()

    for run in runs:
        if not isinstance(run, dict):
            continue
        driver = run.get("tool", {}).get("driver", {})
        driver = driver if isinstance(driver, dict) else {}
        if driver.get("semanticVersion"):
            versions.add(_markdown_text(driver["semanticVersion"]))

        rule_names: dict[str, str] = {}
        rules = driver.get("rules", [])
        for rule in rules if isinstance(rules, list) else []:
            if not isinstance(rule, dict):
                continue
            rule_id = str(rule.get("id") or _rule_name(rule))
            name = _rule_name(rule)
            rule_names[rule_id] = name
            checks.setdefault(name, CheckSummary(help_uri=_safe_http_url(rule.get("helpUri", ""))))

        results = run.get("results", [])
        for result in results if isinstance(results, list) else []:
            if not isinstance(result, dict):
                continue
            rule_id = str(result.get("ruleId") or "Unknown check")
            name = rule_names.get(rule_id, _markdown_text(rule_id))
            level = str(result.get("level") or "none").lower()
            checks.setdefault(name, CheckSummary()).add(level)
            totals[level if level in {"error", "warning", "note"} else "other"] += 1

    return checks, totals, versions


def _check_rows(checks: dict[str, CheckSummary]) -> list[str]:
    rows: list[str] = []
    for name in sorted(checks, key=str.casefold):
        check = checks[name]
        label = f"[{name}]({check.help_uri})" if check.help_uri else name
        rows.append(
            f"| {label} | {check.error} | {check.warning} | {check.note} | {check.entries} |"
        )
    return rows


def render_summary(
    payload: SarifPayload,
    *,
    repository: str,
    commit_sha: str,
    run_url: str,
) -> str:
    """Build a summary from SARIF without inferring a score the format does not contain."""
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("Scorecard SARIF contains no runs")

    checks, totals, versions = _collect_checks(runs)

    if not checks:
        raise ValueError("Scorecard SARIF contains no represented checks")

    repository_text = _markdown_text(repository)
    commit_text = _markdown_text(commit_sha[:12] or "unknown")
    run_link = _safe_http_url(run_url)
    repo_url = f"https://github.com/{repository}"
    viewer_uri = quote(f"github.com/{repository}", safe="/")
    version_text = ", ".join(sorted(versions)) or "not reported"
    total_entries = sum(totals.values())

    lines = [
        "# OpenSSF Scorecard",
        "",
        f"> Repository: `{repository_text}` · Commit: `{commit_text}` · Scorecard: `{version_text}`",
        "",
        "## Scan overview",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Checks represented | {len(checks)} |",
        f"| SARIF entries | {total_entries} |",
        f"| Error entries | {totals['error']} |",
        f"| Warning entries | {totals['warning']} |",
        f"| Note entries | {totals['note']} |",
        f"| Other entries | {totals['other']} |",
        "",
        "## Results by check",
        "",
        "| Check | Errors | Warnings | Notes | Entries |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    lines.extend(_check_rows(checks))

    links = [
        f"[OpenSSF report](https://securityscorecards.dev/viewer/?uri={viewer_uri})",
        f"[Code scanning]({repo_url}/security/code-scanning?query=tool%3AScorecard)",
    ]
    if run_link:
        links.append(f"[Workflow run]({run_link})")

    lines.extend(
        [
            "",
            "## Detailed results",
            "",
            " · ".join(links),
            "",
            "> SARIF is the source for this summary and Code Scanning. It represents check entries, "
            "not the canonical aggregate OpenSSF score; use the OpenSSF report for that score.",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Scorecard SARIF file")
    parser.add_argument("--output", type=Path, required=True, help="GitHub summary file")
    parser.add_argument("--repository", required=True, help="GitHub owner/repository")
    parser.add_argument("--commit-sha", required=True, help="Analyzed Git commit")
    parser.add_argument("--run-url", required=True, help="Current GitHub Actions run URL")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = load_sarif(args.input)
    summary = render_summary(
        payload,
        repository=args.repository,
        commit_sha=args.commit_sha,
        run_url=args.run_url,
    )
    with args.output.open("a", encoding="utf-8", newline="\n") as output:
        output.write(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

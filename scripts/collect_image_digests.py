"""Validate build-produced OCI digests for GitOps staging promotion."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Final

DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"sha256:[a-f0-9]{64}")
EXPECTED_FILES: Final[dict[str, str]] = {
    "shipment-api.digest": "shipment_api_digest",
    "tracking-worker.digest": "tracking_worker_digest",
}


def collect_image_digests(directory: Path) -> dict[str, str]:
    """Return the exact two expected digests or reject the handoff."""
    available = {path.name for path in directory.glob("*.digest") if path.is_file()}
    expected = set(EXPECTED_FILES)

    missing = sorted(expected - available)
    if missing:
        raise ValueError(f"missing digest file: {', '.join(missing)}")

    unexpected = sorted(available - expected)
    if unexpected:
        raise ValueError(f"unexpected digest file: {', '.join(unexpected)}")

    digests: dict[str, str] = {}
    for filename, output_name in EXPECTED_FILES.items():
        lines = (directory / filename).read_text(encoding="utf-8").splitlines()
        if len(lines) != 1 or DIGEST_PATTERN.fullmatch(lines[0]) is None:
            raise ValueError(f"invalid OCI digest in {filename}")
        digests[output_name] = lines[0]
    return digests


def write_github_outputs(path: Path, digests: dict[str, str]) -> None:
    """Append validated values using the GitHub Actions output-file protocol."""
    with path.open("a", encoding="utf-8", newline="\n") as output:
        for name in EXPECTED_FILES.values():
            output.write(f"{name}={digests[name]}\n")


def render_summary(digests: dict[str, str], *, source_sha: str) -> str:
    """Render the validated handoff without shortening deployable digests."""
    return "\n".join(
        [
            "# Staging promotion inputs",
            "",
            f"> Source commit: `{source_sha[:12]}`",
            "",
            "| Service | OCI manifest digest |",
            "| --- | --- |",
            f"| shipment-api | `{digests['shipment_api_digest']}` |",
            f"| tracking-worker | `{digests['tracking_worker_digest']}` |",
            "",
            "Both digests were collected from this workflow run after image scanning, SBOM "
            "generation, and attestations completed.",
            "",
        ]
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        digests = collect_image_digests(args.directory)
    except ValueError as exc:
        raise SystemExit(f"digest collection failed: {exc}") from exc

    write_github_outputs(args.output, digests)
    with args.summary.open("a", encoding="utf-8", newline="\n") as summary:
        summary.write(render_summary(digests, source_sha=args.source_sha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

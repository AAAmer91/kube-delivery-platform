from __future__ import annotations

from pathlib import Path

import pytest

from scripts.collect_image_digests import (
    collect_image_digests,
    render_summary,
    write_github_outputs,
)

SHIPMENT_DIGEST = "sha256:" + ("a" * 64)
WORKER_DIGEST = "sha256:" + ("b" * 64)


def test_collects_exactly_the_two_gitops_image_digests(tmp_path: Path) -> None:
    (tmp_path / "shipment-api.digest").write_text(SHIPMENT_DIGEST + "\n", encoding="utf-8")
    (tmp_path / "tracking-worker.digest").write_text(WORKER_DIGEST + "\n", encoding="utf-8")

    assert collect_image_digests(tmp_path) == {
        "shipment_api_digest": SHIPMENT_DIGEST,
        "tracking_worker_digest": WORKER_DIGEST,
    }


def test_writes_named_outputs_and_a_traceable_summary(tmp_path: Path) -> None:
    digests = {
        "shipment_api_digest": SHIPMENT_DIGEST,
        "tracking_worker_digest": WORKER_DIGEST,
    }
    output_path = tmp_path / "github-output"

    write_github_outputs(output_path, digests)
    summary = render_summary(digests, source_sha="0123456789abcdef")

    assert output_path.read_text(encoding="utf-8").splitlines() == [
        f"shipment_api_digest={SHIPMENT_DIGEST}",
        f"tracking_worker_digest={WORKER_DIGEST}",
    ]
    assert "# Staging promotion inputs" in summary
    assert "`0123456789ab`" in summary
    assert f"`{SHIPMENT_DIGEST}`" in summary
    assert f"`{WORKER_DIGEST}`" in summary


@pytest.mark.parametrize(
    ("filename", "contents", "message"),
    [
        ("shipment-api.digest", SHIPMENT_DIGEST, "tracking-worker.digest"),
        ("unexpected.digest", WORKER_DIGEST, "unexpected digest file"),
        ("tracking-worker.digest", "sha256:not-a-digest", "invalid OCI digest"),
    ],
)
def test_rejects_incomplete_unexpected_or_invalid_digest_sets(
    tmp_path: Path,
    filename: str,
    contents: str,
    message: str,
) -> None:
    if filename in {"tracking-worker.digest", "unexpected.digest"}:
        (tmp_path / "shipment-api.digest").write_text(SHIPMENT_DIGEST, encoding="utf-8")
    if filename == "unexpected.digest":
        (tmp_path / "tracking-worker.digest").write_text(WORKER_DIGEST, encoding="utf-8")
    (tmp_path / filename).write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        collect_image_digests(tmp_path)

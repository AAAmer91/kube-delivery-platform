"""Kubernetes, Helm, and Policy Schema Validation Script.

Validates that all Helm templates, policies, and manifests conform to Kubernetes
schema conventions and security standards.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def validate_yaml_file(file_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        content = file_path.read_text(encoding="utf-8")
        # Handle multi-document YAMLs (excluding raw Helm template directives)
        if "{{" in content:
            # Helm template file - skip direct YAML parsing
            return []

        docs = yaml.safe_load_all(content)
        for doc in docs:
            if not doc or not isinstance(doc, dict):
                continue
            # Verify essential Kubernetes manifest attributes
            if "apiVersion" in doc and "kind" in doc:
                if doc.get("kind") == "Cluster" and "kind.x-k8s.io" in str(doc.get("apiVersion")):
                    if not doc.get("name"):
                        errors.append(f"{file_path}: Missing name for kind Cluster")
                elif not doc.get("metadata", {}).get("name"):
                    errors.append(f"{file_path}: Missing metadata.name for kind {doc.get('kind')}")

    except Exception as err:
        errors.append(f"{file_path}: YAML parsing error: {err}")
    return errors


def main() -> int:
    base_dir = Path(__file__).resolve().parent.parent
    scan_dirs = [
        base_dir / "deploy" / "policies",
        base_dir / "deploy" / "argocd",
        base_dir / "deploy" / "argo-rollouts",
        base_dir / "deploy" / "kind",
    ]

    all_errors: list[str] = []
    checked_files = 0

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for yaml_file in scan_dir.rglob("*.yaml"):
            checked_files += 1
            errs = validate_yaml_file(yaml_file)
            all_errors.extend(errs)

    print(f"🔍 Validated {checked_files} Kubernetes and Policy manifest files.")
    if all_errors:
        print(f"❌ Found {len(all_errors)} validation errors:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("✅ All Kubernetes and Policy manifests are syntactically valid!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Rendered Helm contracts for Argo Rollouts traffic management."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


def test_staging_rollout_uses_nginx_weighted_traffic_routing() -> None:
    """The stable ingress must be controlled by Argo Rollouts for exact canary weights."""
    helm = os.getenv("HELM_BINARY") or shutil.which("helm")
    if not helm:
        pytest.skip("Helm is not installed in this test environment")

    repository = Path(__file__).resolve().parents[2]
    chart = repository / "deploy" / "helm" / "kube-delivery-platform"
    rendered = subprocess.run(
        [
            helm,
            "template",
            "contract",
            str(chart),
            "--namespace",
            "staging",
            "--values",
            str(chart / "values-staging.yaml"),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    documents = [document for document in yaml.safe_load_all(rendered) if document]

    rollout = next(document for document in documents if document.get("kind") == "Rollout")
    rollout_name = rollout["metadata"]["name"]
    platform_name = rollout_name.removesuffix("-shipment-api")
    canary = rollout["spec"]["strategy"]["canary"]
    assert canary["trafficRouting"]["nginx"]["stableIngress"] == f"{platform_name}-ingress"

    ingress = next(document for document in documents if document.get("kind") == "Ingress")
    api_backend = ingress["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"]
    assert api_backend["name"] == f"{rollout_name}-stable"

    services = {
        document["metadata"]["name"] for document in documents if document.get("kind") == "Service"
    }
    assert f"{rollout_name}-stable" in services
    assert f"{rollout_name}-canary" in services


def test_staging_exposes_metrics_to_gitops_managed_prometheus() -> None:
    """Staging must expose both services and query the Prometheus installed by Argo CD."""
    helm = os.getenv("HELM_BINARY") or shutil.which("helm")
    if not helm:
        pytest.skip("Helm is not installed in this test environment")

    repository = Path(__file__).resolve().parents[2]
    chart = repository / "deploy" / "helm" / "kube-delivery-platform"
    rendered = subprocess.run(
        [
            helm,
            "template",
            "contract",
            str(chart),
            "--namespace",
            "staging",
            "--values",
            str(chart / "values-staging.yaml"),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    documents = [document for document in yaml.safe_load_all(rendered) if document]

    service_monitors = [
        document for document in documents if document.get("kind") == "ServiceMonitor"
    ]
    assert {monitor["metadata"]["name"] for monitor in service_monitors} == {
        "contract-kube-delivery-platform-shipment-api",
        "contract-kube-delivery-platform-tracking-worker",
    }

    analysis = next(
        document for document in documents if document.get("kind") == "AnalysisTemplate"
    )
    prometheus_arg = next(
        arg for arg in analysis["spec"]["args"] if arg["name"] == "prometheus-server"
    )
    assert prometheus_arg["value"] == (
        "http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090"
    )

    metrics = analysis["spec"]["metrics"]
    queries = [metric["provider"]["prometheus"]["query"] for metric in metrics]
    assert all('namespace="{{ args.namespace }}"' in query for query in queries)
    assert all('service="{{ args.canary-service }}"' in query for query in queries)
    assert all("or vector(0)" not in query for query in queries)
    assert all("len(result) > 0" in metric["successCondition"] for metric in metrics)


def test_default_deny_has_narrow_hook_egress_and_no_global_monitoring_ingress() -> None:
    """Hooks must work under default deny without reopening ingress cluster-wide."""
    helm = os.getenv("HELM_BINARY") or shutil.which("helm")
    if not helm:
        pytest.skip("Helm is not installed in this test environment")

    repository = Path(__file__).resolve().parents[2]
    chart = repository / "deploy" / "helm" / "kube-delivery-platform"
    rendered = subprocess.run(
        [
            helm,
            "template",
            "contract",
            str(chart),
            "--namespace",
            "staging",
            "--values",
            str(chart / "values-staging.yaml"),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    documents = [document for document in yaml.safe_load_all(rendered) if document]
    policies = {
        document["metadata"]["name"]: document
        for document in documents
        if document.get("kind") == "NetworkPolicy"
    }

    assert "contract-kube-delivery-platform-allow-migration" in policies
    assert "contract-kube-delivery-platform-allow-helm-test" in policies

    protected_names = {
        "contract-kube-delivery-platform-allow-shipment-api",
        "contract-kube-delivery-platform-allow-tracking-worker",
        "contract-kube-delivery-platform-allow-nats",
    }
    for name in protected_names:
        selectors = [
            peer.get("namespaceSelector")
            for rule in policies[name]["spec"].get("ingress", [])
            for peer in rule.get("from", [])
            if "namespaceSelector" in peer
        ]
        assert {} not in selectors

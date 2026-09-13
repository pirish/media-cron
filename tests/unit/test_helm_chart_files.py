"""Unit tests verifying Helm chart metadata, values schema, and template file structure."""

from pathlib import Path

import yaml

CHART_DIR = Path(__file__).resolve().parent.parent.parent / "charts" / "media-cron"
CHART_YAML = CHART_DIR / "Chart.yaml"
VALUES_YAML = CHART_DIR / "values.yaml"
TEMPLATES_DIR = CHART_DIR / "templates"


def test_chart_yaml_metadata():
    """Verify Chart.yaml exists, has apiVersion v2, and correct metadata."""
    assert CHART_YAML.exists(), f"Chart.yaml not found at {CHART_YAML}"
    with open(CHART_YAML, encoding="utf-8") as f:
        chart = yaml.safe_load(f)

    assert chart.get("apiVersion") == "v2"
    assert chart.get("name") == "media-cron"
    assert chart.get("type") == "application"
    assert "version" in chart
    assert "appVersion" in chart


def test_values_yaml_structure_and_defaults():
    """Verify values.yaml defaults workloadType to CronJob and specifies non-root user and mounts."""
    assert VALUES_YAML.exists(), f"values.yaml not found at {VALUES_YAML}"
    with open(VALUES_YAML, encoding="utf-8") as f:
        values = yaml.safe_load(f)

    # Workload default
    assert values.get("workloadType") == "CronJob", "Default workloadType must be CronJob"

    # CronJob parameters
    cronjob = values.get("cronjob", {})
    assert "schedule" in cronjob

    # Security context
    pod_sec = values.get("podSecurityContext", {})
    assert pod_sec.get("runAsUser") == 10001
    assert pod_sec.get("runAsGroup") == 10001

    # Persistence mounts
    persistence = values.get("persistence", {})
    assert "data" in persistence
    assert persistence["data"].get("mountPath") == "/data"
    assert "cache" in persistence
    assert persistence["cache"].get("mountPath") == "/cache"


def test_template_files_exist():
    """Verify standard template files are present in templates directory."""
    assert TEMPLATES_DIR.exists()
    required_templates = [
        "_helpers.tpl",
        "cronjob.yaml",
        "deployment.yaml",
        "serviceaccount.yaml",
        "pvc.yaml",
        "configmap.yaml",
    ]
    for tmpl in required_templates:
        assert (TEMPLATES_DIR / tmpl).exists(), f"Template file missing: {tmpl}"

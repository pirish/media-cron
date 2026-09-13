"""Integration tests for Helm chart linting, templating, and packaging."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CHART_DIR = ROOT_DIR / "charts" / "media-cron"


@pytest.fixture(autouse=True)
def require_helm():
    if not shutil.which("helm"):
        pytest.skip("Helm binary not found on PATH")


def test_helm_lint():
    """Verify that helm lint passes with 0 errors."""
    assert CHART_DIR.exists()
    res = subprocess.run(
        ["helm", "lint", str(CHART_DIR)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Helm lint failed:\n{res.stderr}\n{res.stdout}"


def test_helm_template_default_cronjob():
    """Verify default values render a valid batch/v1 CronJob resource."""
    res = subprocess.run(
        ["helm", "template", "test-cron", str(CHART_DIR)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Helm template failed:\n{res.stderr}\n{res.stdout}"
    manifest = res.stdout
    assert "kind: CronJob" in manifest
    assert "schedule:" in manifest
    assert "/data" in manifest
    assert "kind: Deployment" not in manifest


def test_helm_template_deployment_mode():
    """Verify setting workloadType=Deployment renders an apps/v1 Deployment resource."""
    res = subprocess.run(
        ["helm", "template", "test-deploy", str(CHART_DIR), "--set", "workloadType=Deployment"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Helm template failed:\n{res.stderr}\n{res.stdout}"
    manifest = res.stdout
    assert "kind: Deployment" in manifest
    assert "kind: CronJob" not in manifest


def test_helm_package(tmp_path):
    """Verify that helm package succeeds and produces a chart archive."""
    res = subprocess.run(
        ["helm", "package", str(CHART_DIR), "-d", str(tmp_path)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Helm package failed:\n{res.stderr}\n{res.stdout}"
    packages = list(tmp_path.glob("media-cron-*.tgz"))
    assert len(packages) == 1, f"Expected 1 packaged chart, found {len(packages)}"

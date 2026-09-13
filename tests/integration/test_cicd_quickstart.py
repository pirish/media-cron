"""Integration tests validating Quickstart Scenarios 1 through 5 from quickstart.md."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def test_quickstart_scenario_1_precommit():
    """Scenario 1: Validate pre-commit config structure and validate-config CLI execution."""
    res = subprocess.run(
        [sys.executable, "-m", "pre_commit", "validate-config", ".pre-commit-config.yaml"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Pre-commit config validation failed: {res.stderr}"

    config_path = ROOT_DIR / ".pre-commit-config.yaml"
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Check that system-level pytest hook is defined
    local_repo = next((r for r in data["repos"] if r.get("repo") == "local"), None)
    assert local_repo is not None
    assert any(
        h.get("id") == "pytest" and h.get("language") == "system" for h in local_repo["hooks"]
    )


def test_quickstart_scenario_2_container():
    """Scenario 2: Validate Dockerfile multi-stage build, UID 10001, and standard mount directories."""
    dockerfile = ROOT_DIR / "Dockerfile"
    assert dockerfile.exists()
    content = dockerfile.read_text(encoding="utf-8")

    assert "FROM python:3.11-slim AS builder" in content
    assert "FROM python:3.11-slim" in content
    assert "10001" in content
    assert "/data" in content and "/config" in content and "/cache" in content
    assert 'ENTRYPOINT ["media-cron"]' in content


def test_quickstart_scenario_3_helm_chart():
    """Scenario 3: Validate Helm chart linting and templating for CronJob and Deployment."""
    if not shutil.which("helm"):
        pytest.skip("Helm binary not found on PATH")

    chart_dir = ROOT_DIR / "charts" / "media-cron"

    # Lint
    lint_res = subprocess.run(
        ["helm", "lint", str(chart_dir)], cwd=ROOT_DIR, capture_output=True, text=True
    )
    assert lint_res.returncode == 0, f"Helm lint failed: {lint_res.stderr}"

    # Template default (CronJob)
    tmpl_cron = subprocess.run(
        ["helm", "template", "test-qs", str(chart_dir)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert tmpl_cron.returncode == 0
    assert "kind: CronJob" in tmpl_cron.stdout
    assert "kind: Deployment" not in tmpl_cron.stdout

    # Template Deployment mode
    tmpl_deploy = subprocess.run(
        ["helm", "template", "test-qs", str(chart_dir), "--set", "workloadType=Deployment"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert tmpl_deploy.returncode == 0
    assert "kind: Deployment" in tmpl_deploy.stdout
    assert "kind: CronJob" not in tmpl_deploy.stdout


def test_quickstart_scenario_4_python_package(tmp_path):
    """Scenario 4: Validate package building and twine metadata check."""
    out_dir = tmp_path / "pkg"
    out_dir.mkdir()

    build_res = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(out_dir)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert build_res.returncode == 0, f"Build failed: {build_res.stderr}"

    archives = list(out_dir.glob("*.whl")) + list(out_dir.glob("*.tar.gz"))
    assert len(archives) == 2

    twine_res = subprocess.run(
        [sys.executable, "-m", "twine", "check", "--strict"] + [str(a) for a in archives],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert twine_res.returncode == 0, f"Twine check failed: {twine_res.stderr}"
    assert "PASSED" in twine_res.stdout


def test_quickstart_scenario_5_github_workflows():
    """Scenario 5: Validate GitHub Actions CI and Release workflow syntax and triggers."""
    ci_path = ROOT_DIR / ".github" / "workflows" / "ci.yml"
    rel_path = ROOT_DIR / ".github" / "workflows" / "release.yml"

    assert ci_path.exists()
    assert rel_path.exists()

    with open(ci_path, encoding="utf-8") as f:
        ci = yaml.safe_load(f)
    with open(rel_path, encoding="utf-8") as f:
        rel = yaml.safe_load(f)

    # CI checks
    assert ci.get("permissions", {}).get("contents") == "read"
    assert "lint-and-test" in ci.get("jobs", {})

    # Release checks
    assert rel.get("permissions", {}).get("contents") == "write"
    assert rel.get("permissions", {}).get("packages") == "write"
    assert "publish-container" in rel.get("jobs", {})
    assert "publish-helm" in rel.get("jobs", {})
    assert "publish-python" in rel.get("jobs", {})

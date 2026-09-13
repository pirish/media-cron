"""Unit tests for GitHub Actions CI and Release workflow specifications."""

from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent.parent / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS_DIR / "ci.yml"
RELEASE_WORKFLOW = WORKFLOWS_DIR / "release.yml"


def load_yaml(path: Path) -> dict:
    assert path.exists(), f"Workflow file does not exist: {path}"
    with open(path, encoding="utf-8") as f:
        content = yaml.safe_load(f)
    assert isinstance(content, dict), f"Workflow content is not a dict: {path}"
    return content


def test_ci_workflow_structure_and_triggers():
    """Verify ci.yml triggers on main PRs/pushes and has read-only permissions."""
    ci = load_yaml(CI_WORKFLOW)
    assert ci.get("name") is not None

    # Triggers
    triggers = ci.get("on") or ci.get(True)  # yaml can parse 'on' as boolean True
    assert triggers is not None
    assert "pull_request" in triggers or True in triggers
    assert "push" in triggers

    # Permissions
    permissions = ci.get("permissions", {})
    assert permissions.get("contents") == "read"


def test_ci_workflow_jobs():
    """Verify ci.yml has required validation jobs."""
    ci = load_yaml(CI_WORKFLOW)
    jobs = ci.get("jobs", {})

    # Job: lint-and-test
    assert "lint-and-test" in jobs
    test_job = jobs["lint-and-test"]
    strategy = test_job.get("strategy", {})
    matrix = strategy.get("matrix", {})
    python_versions = [str(v) for v in matrix.get("python-version", [])]
    assert "3.11" in python_versions
    assert "3.12" in python_versions

    # Jobs for artifacts
    assert "container-validate" in jobs
    assert "helm-validate" in jobs
    assert "package-validate" in jobs


def test_release_workflow_triggers_and_permissions():
    """Verify release.yml triggers on version tags with write permissions."""
    rel = load_yaml(RELEASE_WORKFLOW)
    assert rel.get("name") is not None

    # Triggers
    triggers = rel.get("on") or rel.get(True)
    assert triggers is not None
    push_trigger = triggers.get("push", {})
    tags = push_trigger.get("tags", [])
    assert any("v*" in tag for tag in tags)

    # Permissions
    permissions = rel.get("permissions", {})
    assert permissions.get("contents") == "write"
    assert permissions.get("packages") == "write"


def test_release_workflow_jobs_and_dependencies():
    """Verify release.yml contains test-gate, container, helm, and python jobs."""
    rel = load_yaml(RELEASE_WORKFLOW)
    jobs = rel.get("jobs", {})

    # Gating job
    assert "test-gate" in jobs

    # Publishing targets
    assert "publish-container" in jobs
    assert "publish-helm" in jobs
    assert "publish-python" in jobs

    # Dependencies on test-gate
    for target in ["publish-container", "publish-helm", "publish-python"]:
        needs = jobs[target].get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        assert "test-gate" in needs, f"{target} must depend on test-gate"

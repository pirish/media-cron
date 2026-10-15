"""Unit tests for GitHub Actions CI and Release workflow specifications."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS_DIR / "ci.yml"
RELEASE_WORKFLOW = WORKFLOWS_DIR / "release.yml"
CODEOWNERS_FILE = REPO_ROOT / ".github" / "CODEOWNERS"
README_FILE = REPO_ROOT / "README.md"


def load_yaml(path: Path) -> dict:
    assert path.exists(), f"Workflow file does not exist: {path}"
    with open(path, encoding="utf-8") as f:
        content = yaml.safe_load(f)
    assert isinstance(content, dict), f"Workflow content is not a dict: {path}"
    return content


def test_ci_workflow_structure_and_triggers():
    """Verify ci.yml triggers on main PRs (including opening) and pushes, with read-only permissions."""
    ci = load_yaml(CI_WORKFLOW)
    assert ci.get("name") is not None

    # Triggers
    triggers = ci.get("on") or ci.get(True)  # yaml can parse 'on' as boolean True
    assert triggers is not None
    assert "pull_request" in triggers or True in triggers
    pr_config = triggers.get("pull_request", {})
    if isinstance(pr_config, dict) and "types" in pr_config:
        assert "opened" in pr_config["types"]

    assert "push" in triggers
    push_config = triggers.get("push", {})
    if isinstance(push_config, dict) and "branches" in push_config:
        assert "main" in push_config["branches"]

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
    """Verify release.yml triggers on main push and version tags with write permissions."""
    rel = load_yaml(RELEASE_WORKFLOW)
    assert rel.get("name") is not None

    # Triggers
    triggers = rel.get("on") or rel.get(True)
    assert triggers is not None
    push_trigger = triggers.get("push", {})
    tags = push_trigger.get("tags", [])
    assert any("v*" in tag for tag in tags)
    branches = push_trigger.get("branches", [])
    assert "main" in branches

    # Permissions
    permissions = rel.get("permissions", {})
    assert permissions.get("contents") == "write"
    assert permissions.get("packages") == "write"


def test_release_workflow_jobs_and_dependencies():
    """Verify release.yml contains test-gate, create-release, container, helm, and python jobs."""
    rel = load_yaml(RELEASE_WORKFLOW)
    jobs = rel.get("jobs", {})

    # Gating job
    assert "test-gate" in jobs

    # Release creation / semver calculation job
    assert "create-release" in jobs
    assert jobs["create-release"].get("needs") == "test-gate" or "test-gate" in jobs[
        "create-release"
    ].get("needs", [])

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
        assert "create-release" in needs, f"{target} must depend on create-release"


def test_codeowners_file():
    """Verify .github/CODEOWNERS exists and assigns default repository ownership to @pirish."""
    assert CODEOWNERS_FILE.exists(), f"CODEOWNERS file does not exist at {CODEOWNERS_FILE}"
    content = CODEOWNERS_FILE.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert any("* @pirish" in line for line in lines), "CODEOWNERS must assign * to @pirish"


def test_readme_status_badges():
    """Verify README.md contains build status badges at the top."""
    assert README_FILE.exists(), "README.md does not exist"
    content = README_FILE.read_text(encoding="utf-8")
    first_section = "\n".join(content.splitlines()[:15])

    assert "actions/workflows/ci.yml/badge.svg" in first_section
    assert "actions/workflows/release.yml/badge.svg" in first_section


def test_release_workflow_updates_helm_app_version():
    """Verify release.yml updates appVersion in Helm chart before packaging."""
    rel = load_yaml(RELEASE_WORKFLOW)
    publish_helm = rel.get("jobs", {}).get("publish-helm", {})
    steps = publish_helm.get("steps", [])

    app_version_steps = [
        s for s in steps if "appVersion" in s.get("name", "") or "appVersion" in s.get("run", "")
    ]
    assert app_version_steps, "publish-helm must contain a step updating appVersion in Chart.yaml"

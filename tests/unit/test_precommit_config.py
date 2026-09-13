"""Unit tests verifying .pre-commit-config.yaml structure and hook specifications."""

from pathlib import Path

import yaml

PRECOMMIT_CONFIG = Path(__file__).resolve().parent.parent.parent / ".pre-commit-config.yaml"


def load_precommit_config() -> dict:
    assert PRECOMMIT_CONFIG.exists(), f"Configuration file not found: {PRECOMMIT_CONFIG}"
    with open(PRECOMMIT_CONFIG, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), ".pre-commit-config.yaml must parse as a dictionary"
    assert "repos" in data, ".pre-commit-config.yaml must define 'repos'"
    return data


def test_precommit_hygiene_hooks():
    """Verify standard file hygiene hooks are configured."""
    config = load_precommit_config()
    repos = config["repos"]

    # Find pre-commit-hooks repo
    hygiene_repo = next(
        (r for r in repos if "pre-commit-hooks" in r.get("repo", "")),
        None,
    )
    assert hygiene_repo is not None, "pre-commit/pre-commit-hooks repository must be defined"
    hook_ids = {h.get("id") for h in hygiene_repo.get("hooks", [])}

    required_hooks = {
        "trailing-whitespace",
        "end-of-file-fixer",
        "check-yaml",
        "check-toml",
        "check-added-large-files",
    }
    missing = required_hooks - hook_ids
    assert not missing, f"Missing required file hygiene hooks: {missing}"


def test_precommit_ruff_hooks():
    """Verify Astral ruff hooks are configured for linting and formatting."""
    config = load_precommit_config()
    repos = config["repos"]

    ruff_repo = next(
        (r for r in repos if "ruff-pre-commit" in r.get("repo", "")),
        None,
    )
    assert ruff_repo is not None, "astral-sh/ruff-pre-commit repository must be defined"
    hooks = {h.get("id"): h for h in ruff_repo.get("hooks", [])}

    assert "ruff" in hooks, "ruff lint hook must be present"
    assert "ruff-format" in hooks, "ruff-format hook must be present"
    assert "--fix" in hooks["ruff"].get("args", []), "ruff hook should include --fix"


def test_precommit_system_pytest_hook():
    """Verify local system-level pytest hook is configured per Q4 specification."""
    config = load_precommit_config()
    repos = config["repos"]

    local_repo = next(
        (r for r in repos if r.get("repo") == "local"),
        None,
    )
    assert local_repo is not None, "local repo must be defined for system hooks"

    pytest_hook = next(
        (h for h in local_repo.get("hooks", []) if h.get("id") == "pytest"),
        None,
    )
    assert pytest_hook is not None, "pytest hook must be configured in local repo"
    assert pytest_hook.get("entry") == "pytest"
    assert pytest_hook.get("language") == "system"
    assert pytest_hook.get("pass_filenames") is False
    assert pytest_hook.get("always_run") is True

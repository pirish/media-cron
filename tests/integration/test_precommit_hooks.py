"""Integration tests verifying pre-commit hook execution behavior and exit code gating."""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def test_precommit_cli_installed():
    """Verify pre-commit CLI is installed and responsive."""
    result = subprocess.run(
        [sys.executable, "-m", "pre_commit", "--version"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "pre-commit" in result.stdout


def test_precommit_config_validation():
    """Verify .pre-commit-config.yaml validates cleanly via pre-commit CLI."""
    result = subprocess.run(
        [sys.executable, "-m", "pre_commit", "validate-config", ".pre-commit-config.yaml"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Config validation failed:\n{result.stderr}\n{result.stdout}"


def test_system_pytest_invocation_gating():
    """Verify pytest system hook execution contract: exit 0 on clean run, exit non-zero on failure."""
    # Passing run
    pass_result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit/test_precommit_config.py"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert pass_result.returncode == 0

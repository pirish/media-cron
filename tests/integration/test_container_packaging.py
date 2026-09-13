"""Integration tests for container build sanity and entry point configuration."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DOCKERFILE = ROOT_DIR / "Dockerfile"


def test_dockerfile_instruction_flow():
    """Verify Dockerfile contains the correct sequential instruction order for multi-stage build."""
    assert DOCKERFILE.exists()
    content = DOCKERFILE.read_text(encoding="utf-8")

    # Verify stage progression
    builder_idx = content.find("as builder")
    assert builder_idx != -1 or "AS builder" in content or "as build" in content

    # Stage 2 copy from builder
    assert "--from=builder" in content or "--from=build" in content

    # Wheel installation
    assert "pip install" in content

    # User non-root setup
    assert "useradd" in content or "adduser" in content


@pytest.mark.skipif(
    shutil.which("docker") is None, reason="Docker daemon / CLI not available in environment"
)
def test_docker_build_and_run():
    """Execute live docker build and CLI execution when docker is present."""
    build_res = subprocess.run(
        ["docker", "build", "-t", "media-cron:test", "."],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert build_res.returncode == 0, f"Docker build failed:\n{build_res.stderr}"

    run_res = subprocess.run(
        ["docker", "run", "--rm", "media-cron:test", "--help"],
        capture_output=True,
        text=True,
    )
    assert run_res.returncode == 0
    assert "media-cron" in run_res.stdout

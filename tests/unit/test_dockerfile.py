"""Unit tests for Dockerfile specification, non-root security, and .dockerignore rules."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DOCKERFILE = ROOT_DIR / "Dockerfile"
DOCKERIGNORE = ROOT_DIR / ".dockerignore"


def test_dockerignore_rules():
    """Verify .dockerignore excludes virtual environments, git, tests, and specs."""
    assert DOCKERIGNORE.exists(), ".dockerignore file must exist"
    content = DOCKERIGNORE.read_text(encoding="utf-8")

    expected_patterns = [".git", ".venv", "tests", "specs"]
    for pattern in expected_patterns:
        assert any(
            pattern in line for line in content.splitlines()
        ), f"Pattern '{pattern}' should be in .dockerignore"


def test_dockerfile_multi_stage_structure():
    """Verify Dockerfile uses a multi-stage build starting from python:3.11-slim."""
    assert DOCKERFILE.exists(), "Dockerfile must exist"
    lines = DOCKERFILE.read_text(encoding="utf-8").splitlines()

    from_lines = [line for line in lines if line.strip().upper().startswith("FROM")]
    assert (
        len(from_lines) >= 2
    ), "Dockerfile must define a multi-stage build (at least 2 FROM instructions)"
    assert any(
        "python:3.11-slim" in line for line in from_lines
    ), "Dockerfile should use python:3.11-slim base"


def test_dockerfile_non_root_security_and_user():
    """Verify non-root user UID 10001 is created and configured as runtime user."""
    assert DOCKERFILE.exists()
    content = DOCKERFILE.read_text(encoding="utf-8")

    assert "10001" in content, "Non-root UID/GID 10001 must be specified"
    assert any(
        line.strip().upper().startswith("USER") and ("10001" in line or "appuser" in line)
        for line in content.splitlines()
    ), "Dockerfile must switch to non-root user (USER appuser or USER 10001)"


def test_dockerfile_volume_mounts_and_entrypoint():
    """Verify standard mount directories and media-cron entrypoint."""
    assert DOCKERFILE.exists()
    content = DOCKERFILE.read_text(encoding="utf-8")

    for dir_path in ["/data", "/config", "/cache"]:
        assert dir_path in content, f"Volume target directory {dir_path} must be created or mounted"

    assert 'ENTRYPOINT ["media-cron"]' in content or 'ENTRYPOINT ["media-cron"]' in content

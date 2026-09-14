"""Integration test for building source/wheel packages and verifying metadata via twine."""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def test_package_build_and_twine_validation(tmp_path):
    """Verify that python -m build produces compliant distribution packages validated by twine."""
    out_dir = tmp_path / "dist"
    out_dir.mkdir()

    # Step 1: Build packages
    build_res = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(out_dir)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    build_err = f"Package build failed:\n{build_res.stderr}\n{build_res.stdout}"
    assert build_res.returncode == 0, build_err

    # Step 2: Confirm artifacts exist
    sdist_files = list(out_dir.glob("*.tar.gz"))
    wheel_files = list(out_dir.glob("*.whl"))

    assert len(sdist_files) == 1, f"Expected 1 sdist archive, found {len(sdist_files)}"
    assert len(wheel_files) == 1, f"Expected 1 wheel archive, found {len(wheel_files)}"

    # Step 3: Run twine check --strict
    twine_res = subprocess.run(
        [sys.executable, "-m", "twine", "check", "--strict"]
        + [str(p) for p in (sdist_files + wheel_files)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    twine_err = f"Twine validation failed:\n{twine_res.stderr}\n{twine_res.stdout}"
    assert twine_res.returncode == 0, twine_err
    assert "PASSED" in twine_res.stdout

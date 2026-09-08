import json
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def test_dry_run_simulation_cli(tmp_path: Path):
    source = tmp_path / "downloads"
    staging = tmp_path / "staging"
    destination = tmp_path / "library"

    source.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)

    # Populate test files in source
    movie_file = source / "Movie.Sample.2024.1080p.mkv"
    movie_file.write_bytes(b"mock video data" * 100)
    original_mtime = movie_file.stat().st_mtime
    original_size = movie_file.stat().st_size

    # Run organize command in dry-run with json format
    result = runner.invoke(
        app,
        [
            "organize",
            "--source",
            str(source),
            "--staging",
            str(staging),
            "--destination",
            str(destination),
            "--dry-run",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, f"Command failed: {result.stdout}"

    # Parse JSON output
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert data["exit_code"] == 0
    assert data["total_scanned"] >= 1
    assert "operations" in data

    # Assert source file was NOT modified or moved
    assert movie_file.exists()
    assert movie_file.stat().st_size == original_size
    assert movie_file.stat().st_mtime == original_mtime
    # Staging and destination should be untouched
    assert not (staging / "Movie.Sample.2024.1080p.mkv").exists()

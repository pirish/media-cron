import fcntl
import json
import time
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def test_quickstart_scenario_a_dry_run(tmp_path: Path):
    source = tmp_path / "downloads" / "Movie.Sample.2024.1080p-GROUP"
    staging = tmp_path / "staging"
    destination = tmp_path / "library"

    source.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)

    movie = source / "movie.mkv"
    # valid MKV header
    movie.write_bytes(b"\x1a\x45\xdf\xa3" + b"movie content" * 100)
    sub = source / "movie.en.srt"
    sub.write_text("1\n00:00:01 --> 00:00:02\nSubtitle")
    junk = source / "release.nfo"
    junk.write_text("info")

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

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert data["exit_code"] == 0

    # Assert source files completely untouched
    assert movie.exists()
    assert sub.exists()
    assert junk.exists()
    # Staging untouched
    assert not (staging / "movie.mkv").exists()


def test_quickstart_scenario_b_live_staging_and_seeding(tmp_path: Path):
    source = tmp_path / "downloads" / "Interstellar.2014.1080p-GRP"
    staging = tmp_path / "staging"
    destination = tmp_path / "library"
    seed = tmp_path / "seed"

    source.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    seed.mkdir(parents=True, exist_ok=True)

    movie = source / "Interstellar.2014.1080p.mkv"
    movie.write_bytes(b"\x1a\x45\xdf\xa3" + b"interstellar data" * 100)
    junk = source / "release.nfo"
    junk.write_text("clutter")

    start_time = time.time()
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
            "--seed-dir",
            str(seed),
            "--mode",
            "hardlink",
            "--format",
            "text",
        ],
    )
    duration = time.time() - start_time

    assert result.exit_code == 0, f"Error: {result.stdout}"
    # SC-004 benchmark check
    assert duration < 5.0, f"Execution took {duration}s, expected < 5s"

    # Destination library has organized structure
    expected_movie = destination / "Movies" / "Interstellar (2014)" / "Interstellar (2014).mkv"
    assert expected_movie.exists()

    # Seed directory has original filename preserved
    expected_seed = seed / "Interstellar.2014.1080p.mkv"
    assert expected_seed.exists()
    assert expected_movie.stat().st_ino == expected_seed.stat().st_ino

    # Junk is removed
    assert not junk.exists()


def test_quickstart_scenario_c_lock_contention(tmp_path: Path):
    source = tmp_path / "downloads"
    staging = tmp_path / "staging"
    destination = tmp_path / "library"

    source.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)

    # Acquire lock in staging
    lock_file = staging / ".media-cron.lock"
    fd = lock_file.open("w")
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    try:
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
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert data["exit_code"] == 1
        assert any("locked" in err.lower() for err in data["errors"])
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()

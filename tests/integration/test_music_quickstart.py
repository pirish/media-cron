import json
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def test_quickstart_scenario_1_drop_folder_ingestion(tmp_path: Path):
    """Scenario 1: Drop-Folder Ingestion for External Music Library Managers (Beets Spool Mode)."""
    staging = tmp_path / "staging"
    dest = tmp_path / "dest"
    beets_drop = tmp_path / "beets_drop"

    staging.mkdir()
    dest.mkdir()
    beets_drop.mkdir()

    release_dir = staging / "Daft_Punk_Discovery"
    release_dir.mkdir()
    t1 = release_dir / "01_one_more_time.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)
    t2 = release_dir / "02_aerodynamic.flac"
    t2.write_bytes(b"fLaC" + b"\x00" * 50)
    art = release_dir / "cover.jpg"
    art.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
    cue = release_dir / "album.cue"
    cue.write_text('FILE "Discovery.flac" WAVE\n  TRACK 01 AUDIO\n', encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            str(staging),
            "--staging",
            str(staging),
            "--destination",
            str(dest),
            "--music-spool-dir",
            str(beets_drop),
            "--music-mode",
            "spool",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["exit_code"] == 0
    assert payload["music_summary"]["spooled_releases"] >= 1

    spooled_release = beets_drop / "Daft_Punk_Discovery"
    assert spooled_release.exists()
    assert (spooled_release / "01_one_more_time.flac").exists()
    assert (spooled_release / "02_aerodynamic.flac").exists()
    assert (spooled_release / "cover.jpg").exists()
    assert (spooled_release / "album.cue").exists()

    # Verify no .incoming_* temporary directories remain
    incoming_dirs = list(beets_drop.glob(".incoming_*"))
    assert len(incoming_dirs) == 0


def test_quickstart_scenario_2_post_ingest_command_hook(tmp_path: Path):
    """Scenario 2: Post-Ingest Command Hook Execution."""
    source_dir = tmp_path / "staging" / "Daft_Punk_Discovery"
    source_dir.mkdir(parents=True)
    t1 = source_dir / "01_one_more_time.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)

    beets_drop = tmp_path / "beets_drop"
    beets_drop.mkdir()

    hook_log = tmp_path / "hook.log"

    result = runner.invoke(
        app,
        [
            "test-music-spool",
            str(source_dir),
            "--spool-dir",
            str(beets_drop),
            "--post-command",
            f"echo 'Imported release at {{release_path}}' > {hook_log}",
            "--no-dry-run",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["post_command_exit_code"] == 0
    assert hook_log.exists()
    log_content = hook_log.read_text(encoding="utf-8").strip()
    assert f"Imported release at {beets_drop}/Daft_Punk_Discovery" in log_content


def test_quickstart_scenario_3_direct_library_organization(tmp_path: Path):
    """Scenario 3: Embedded Tag Extraction & Direct Library Organization."""
    staging = tmp_path / "staging"
    dest = tmp_path / "dest"
    staging.mkdir()
    dest.mkdir()

    release_dir = staging / "Daft Punk - Discovery (2001)"
    release_dir.mkdir()
    t1 = release_dir / "01 - One More Time.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)
    art = release_dir / "cover.jpg"
    art.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            str(staging),
            "--staging",
            str(staging),
            "--destination",
            str(dest),
            "--music-mode",
            "direct",
            "--no-music-lookup",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["exit_code"] == 0
    assert payload["music_summary"]["organized_tracks"] >= 1

    target_album_dir = dest / "Music" / "Daft Punk" / "Discovery (2001)"
    assert target_album_dir.exists()
    assert (target_album_dir / "01 - One More Time.flac").exists()
    assert (target_album_dir / "cover.jpg").exists()


def test_quickstart_scenario_4_diagnostic_inspection(tmp_path: Path):
    """Scenario 4: Diagnostic Inspection (test-music-identify)."""
    track_file = tmp_path / "01 - One More Time.flac"
    track_file.write_bytes(b"fLaC" + b"\x00" * 50)

    result = runner.invoke(
        app,
        [
            "test-music-identify",
            str(track_file),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["track"] is not None
    assert payload["track"]["title"] == "One More Time"
    assert payload["track"]["format"] == "flac"


def test_quickstart_scenario_5_dry_run_simulation(tmp_path: Path):
    """Scenario 5: Dry-Run Simulation & Safety."""
    staging = tmp_path / "staging"
    dest = tmp_path / "dest"
    beets_drop = tmp_path / "beets_drop"
    staging.mkdir()
    dest.mkdir()
    beets_drop.mkdir()

    release_dir = staging / "Daft_Punk_Discovery"
    release_dir.mkdir()
    t1 = release_dir / "01_one_more_time.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)
    art = release_dir / "cover.jpg"
    art.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            str(staging),
            "--staging",
            str(staging),
            "--destination",
            str(dest),
            "--music-spool-dir",
            str(beets_drop),
            "--dry-run",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["music_summary"] is not None

    # No files created in beets_drop
    assert not (beets_drop / "Daft_Punk_Discovery").exists()
    # Staging files untouched
    assert t1.exists()
    assert art.exists()

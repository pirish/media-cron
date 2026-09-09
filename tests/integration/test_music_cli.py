import json
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def test_cli_music_spool_mode(tmp_path: Path):
    source = tmp_path / "source"
    dest = tmp_path / "destination"
    staging = tmp_path / "staging"
    spool = tmp_path / "spool"
    source.mkdir()
    dest.mkdir()
    staging.mkdir()
    spool.mkdir()

    album_dir = source / "Daft Punk - Discovery"
    album_dir.mkdir()
    t1 = album_dir / "01 - One More Time.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)
    art = album_dir / "cover.jpg"
    art.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    result = runner.invoke(
        app,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            str(dest),
            "--staging",
            str(staging),
            "--music-mode",
            "spool",
            "--music-spool-dir",
            str(spool),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["exit_code"] == 0
    assert payload.get("music_summary") is not None
    assert payload["music_summary"]["spooled_releases"] >= 1

    spooled_release = spool / "Daft Punk - Discovery"
    assert spooled_release.exists()
    assert (spooled_release / "01 - One More Time.flac").exists()
    assert (spooled_release / "cover.jpg").exists()


def test_cli_music_spool_dir_infers_spool_mode(tmp_path: Path):
    source = tmp_path / "source"
    dest = tmp_path / "destination"
    staging = tmp_path / "staging"
    spool = tmp_path / "spool"
    source.mkdir()
    dest.mkdir()
    staging.mkdir()
    spool.mkdir()

    album_dir = source / "Radiohead - OK Computer"
    album_dir.mkdir()
    t1 = album_dir / "01 - Airbag.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)

    result = runner.invoke(
        app,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            str(dest),
            "--staging",
            str(staging),
            "--music-spool-dir",
            str(spool),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["exit_code"] == 0
    assert payload.get("music_summary") is not None
    assert payload["music_summary"]["spooled_releases"] >= 1

    spooled_release = spool / "Radiohead - OK Computer"
    assert spooled_release.exists()
    assert (spooled_release / "01 - Airbag.flac").exists()


def test_cli_music_direct_mode(tmp_path: Path):
    source = tmp_path / "source"
    dest = tmp_path / "destination"
    staging = tmp_path / "staging"
    source.mkdir()
    dest.mkdir()
    staging.mkdir()

    album_dir = source / "The Beatles - Abbey Road (1969)"
    album_dir.mkdir()
    t1 = album_dir / "01 - Come Together.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)

    result = runner.invoke(
        app,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            str(dest),
            "--staging",
            str(staging),
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
    assert payload.get("music_summary") is not None
    assert payload["music_summary"]["organized_tracks"] >= 1

    dest_track = dest / "Music" / "The Beatles" / "Abbey Road (1969)" / "01 - Come Together.flac"
    assert dest_track.exists()


def test_cli_music_dry_run(tmp_path: Path):
    source = tmp_path / "source"
    dest = tmp_path / "destination"
    staging = tmp_path / "staging"
    source.mkdir()
    dest.mkdir()
    staging.mkdir()

    album_dir = source / "Pink Floyd - Animals (1977)"
    album_dir.mkdir()
    t1 = album_dir / "01 - Dogs.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)

    result = runner.invoke(
        app,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            str(dest),
            "--staging",
            str(staging),
            "--dry-run",
            "--music-mode",
            "direct",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload.get("music_summary") is not None

    # Destination should have zero mutations
    assert not (dest / "Music").exists()
    assert t1.exists()


def test_cli_no_music_flag(tmp_path: Path):
    source = tmp_path / "source"
    dest = tmp_path / "destination"
    staging = tmp_path / "staging"
    source.mkdir()
    dest.mkdir()
    staging.mkdir()

    album_dir = source / "Pink Floyd - Animals (1977)"
    album_dir.mkdir()
    t1 = album_dir / "01 - Dogs.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)

    result = runner.invoke(
        app,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            str(dest),
            "--staging",
            str(staging),
            "--no-music",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["exit_code"] == 0
    assert not (dest / "Music").exists()


def test_cli_music_post_command(tmp_path: Path):
    source = tmp_path / "source"
    dest = tmp_path / "destination"
    staging = tmp_path / "staging"
    spool = tmp_path / "spool"
    source.mkdir()
    dest.mkdir()
    staging.mkdir()
    spool.mkdir()

    album_dir = source / "Kraftwerk - Computer World"
    album_dir.mkdir()
    t1 = album_dir / "01 - Computer World.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)

    hook_file = tmp_path / "hook_executed.txt"

    result = runner.invoke(
        app,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            str(dest),
            "--staging",
            str(staging),
            "--music-mode",
            "spool",
            "--music-spool-dir",
            str(spool),
            "--music-post-command",
            f"touch {hook_file}",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload.get("music_summary") is not None
    assert payload["music_summary"]["post_commands_run"] >= 1
    assert hook_file.exists()

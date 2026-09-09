import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.metadata.models import MusicCatalogMatch

runner = CliRunner()


def test_cli_test_music_identify_track_text(tmp_path: Path):
    track_file = tmp_path / "01 - Pink Floyd - Time.flac"
    track_file.write_bytes(b"fLaC" + b"\x00" * 50)

    result = runner.invoke(
        app,
        [
            "test-music-identify",
            str(track_file),
            "--no-lookup",
            "--format",
            "text",
        ],
    )
    assert result.exit_code == 0
    assert "Time" in result.stdout
    assert "Pink Floyd" in result.stdout


def test_cli_test_music_identify_track_json(tmp_path: Path):
    track_file = tmp_path / "01 - Pink Floyd - Time.flac"
    track_file.write_bytes(b"fLaC" + b"\x00" * 50)

    result = runner.invoke(
        app,
        [
            "test-music-identify",
            str(track_file),
            "--no-lookup",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert "track" in payload
    assert payload["track"]["title"] == "Time"
    assert payload["track"]["artist"] == "Pink Floyd"
    assert payload["release_bundle"] is not None
    assert payload["catalog_match"] is None


def test_cli_test_music_identify_with_lookup(tmp_path: Path):
    album_dir = tmp_path / "Dark Side of the Moon"
    album_dir.mkdir()
    track_file = album_dir / "01 - Speak to Me.flac"
    track_file.write_bytes(b"fLaC" + b"\x00" * 50)

    match = MusicCatalogMatch(
        title="The Dark Side of the Moon",
        artist="Pink Floyd",
        release_id="mb-dark-side-123",
        provider="musicbrainz",
        confidence=0.98,
        year=1973,
        track_count=10,
    )

    with patch("media_cron.metadata.music_identifier.MusicIdentifier.identify", return_value=match):
        result = runner.invoke(
            app,
            [
                "test-music-identify",
                str(album_dir),
                "--lookup",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["status"] == "success"
        assert payload["catalog_match"] is not None
        assert payload["catalog_match"]["release_id"] == "mb-dark-side-123"
        assert payload["catalog_match"]["confidence"] == 0.98


def test_cli_test_music_spool_dry_run(tmp_path: Path):
    source_dir = tmp_path / "staging" / "Daft Punk - Discovery"
    source_dir.mkdir(parents=True)
    t1 = source_dir / "01 - One More Time.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)
    art = source_dir / "cover.jpg"
    art.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "test-music-spool",
            str(source_dir),
            "--spool-dir",
            str(spool_dir),
            "--dry-run",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["dry_run"] is True
    assert len(payload["files_transferred"]) == 2
    # Ensure spool dir was NOT mutated
    assert not (spool_dir / "Daft Punk - Discovery").exists()


def test_cli_test_music_spool_execution(tmp_path: Path):
    source_dir = tmp_path / "staging" / "Daft Punk - Discovery"
    source_dir.mkdir(parents=True)
    t1 = source_dir / "01 - One More Time.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)
    art = source_dir / "cover.jpg"
    art.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "test-music-spool",
            str(source_dir),
            "--spool-dir",
            str(spool_dir),
            "--no-dry-run",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["dry_run"] is False

    target_release = spool_dir / "Daft Punk - Discovery"
    assert target_release.exists()
    assert (target_release / "01 - One More Time.flac").exists()
    assert (target_release / "cover.jpg").exists()

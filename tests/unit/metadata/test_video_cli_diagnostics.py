import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def test_cli_test_video_identify_single_file_text(tmp_path: Path):
    video_file = tmp_path / "Breaking.Bad.S02E05.Breakage.1080p.WEB-DL.mkv"
    video_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    result = runner.invoke(
        app,
        [
            "test-video-identify",
            str(video_file),
            "--format",
            "text",
        ],
    )
    assert result.exit_code == 0
    assert "Breaking Bad" in result.stdout
    assert "1080p" in result.stdout
    assert "S02E05" in result.stdout


def test_cli_test_video_identify_single_file_json(tmp_path: Path):
    video_file = tmp_path / "Breaking.Bad.S02E05.Breakage.1080p.WEB-DL.mkv"
    video_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    result = runner.invoke(
        app,
        [
            "test-video-identify",
            str(video_file),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert "track" in payload
    assert payload["track"]["show_title"] == "Breaking Bad"
    assert payload["track"]["season_number"] == 2
    assert payload["track"]["episode_number"] == 5
    assert payload["track"]["resolution"] == "1080p"


def test_cli_test_video_identify_bundle_dir_json(tmp_path: Path):
    bundle_dir = tmp_path / "Dune.Part.Two.2024.2160p"
    bundle_dir.mkdir()
    (bundle_dir / "Dune.Part.Two.2024.2160p.mkv").write_bytes(b"\x1a\x45\xdf\xa3" + b"dune" * 50)
    (bundle_dir / "Dune.Part.Two.2024.2160p.en.forced.srt").write_text(
        "1\n00:00:01 --> 00:00:02\nSub"
    )

    result = runner.invoke(
        app,
        [
            "test-video-identify",
            str(bundle_dir),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert "release_bundle" in payload
    assert payload["release_bundle"]["total_videos"] == 1
    assert "Dune.Part.Two.2024.2160p.en.forced.srt" in payload["release_bundle"]["companion_files"]


def test_cli_test_video_spool_dry_run_json(tmp_path: Path):
    source_dir = tmp_path / "Dune.Part.Two.2024.2160p"
    source_dir.mkdir()
    (source_dir / "Dune.Part.Two.2024.2160p.mkv").write_bytes(b"\x1a\x45\xdf\xa3" + b"dune" * 50)
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "test-video-spool",
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
    assert not (spool_dir / "Dune.Part.Two.2024.2160p").exists()


def test_cli_test_video_spool_live(tmp_path: Path):
    source_dir = tmp_path / "Dune.Part.Two.2024.2160p"
    source_dir.mkdir()
    (source_dir / "Dune.Part.Two.2024.2160p.mkv").write_bytes(b"\x1a\x45\xdf\xa3" + b"dune" * 50)
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "test-video-spool",
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
    assert (spool_dir / "Dune.Part.Two.2024.2160p" / "Dune.Part.Two.2024.2160p.mkv").exists()


def test_cli_test_media_server_notify_dry_run_json():
    result = runner.invoke(
        app,
        [
            "test-media-server-notify",
            "--provider",
            "jellyfin",
            "--url",
            "http://localhost:8096",
            "--token",
            "test-token",
            "--dry-run",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["dry_run"] is True
    assert payload["server_type"] == "jellyfin"
    assert payload["status_code"] == 204


def test_cli_test_media_server_notify_live():
    mock_resp = MagicMock()
    mock_resp.status = 204
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        result = runner.invoke(
            app,
            [
                "test-media-server-notify",
                "--provider",
                "plex",
                "--url",
                "http://localhost:32400",
                "--token",
                "plex-token",
                "--library-id",
                "1",
                "--no-dry-run",
                "--format",
                "text",
            ],
        )
        assert result.exit_code == 0
        assert "Successfully notified plex library rescan" in result.stdout
        assert mock_open.call_count == 1

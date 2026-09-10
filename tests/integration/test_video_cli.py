from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def test_cli_video_spool_mode_flag(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    staging = tmp_path / "staging"
    staging.mkdir()
    spool = tmp_path / "spool"
    spool.mkdir()

    rel_dir = source / "Succession.S04E01.1080p"
    rel_dir.mkdir()
    rel = rel_dir / "Succession.S04E01.1080p.mkv"
    rel.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 100)

    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            str(source),
            "--staging",
            str(staging),
            "--video-spool-dir",
            str(spool),
            "--mode",
            "copy",
            "--format",
            "text",
        ],
    )
    assert result.exit_code == 0
    assert (spool / "Succession.S04E01.1080p" / "Succession.S04E01.1080p.mkv").exists()


def test_cli_video_direct_mode_flag(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    staging = tmp_path / "staging"
    staging.mkdir()
    dest = tmp_path / "destination"
    dest.mkdir()

    rel = source / "Oppenheimer.2023.2160p.mkv"
    rel.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 100)

    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            str(source),
            "--staging",
            str(staging),
            "--destination",
            str(dest),
            "--video-mode",
            "direct",
            "--mode",
            "copy",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    expected_movie = dest / "Movies" / "Oppenheimer (2023)" / "Oppenheimer (2023) [2160p].mkv"
    assert expected_movie.exists()


def test_cli_video_dry_run_flag(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    staging = tmp_path / "staging"
    staging.mkdir()
    dest = tmp_path / "destination"
    dest.mkdir()

    rel = source / "Oppenheimer.2023.2160p.mkv"
    rel.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 100)

    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            str(source),
            "--staging",
            str(staging),
            "--destination",
            str(dest),
            "--video-mode",
            "direct",
            "--dry-run",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    expected_movie = dest / "Movies" / "Oppenheimer (2023)" / "Oppenheimer (2023) [2160p].mkv"
    assert not expected_movie.exists()


def test_cli_media_server_flags(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    staging = tmp_path / "staging"
    staging.mkdir()
    dest = tmp_path / "destination"
    dest.mkdir()

    rel = source / "Severance.S01E01.1080p.mkv"
    rel.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 100)

    mock_resp = MagicMock()
    mock_resp.status = 204
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        result = runner.invoke(
            app,
            [
                "process",
                "--source",
                str(source),
                "--staging",
                str(staging),
                "--destination",
                str(dest),
                "--video-mode",
                "direct",
                "--media-server",
                "--media-server-provider",
                "jellyfin",
                "--media-server-url",
                "http://jellyfin:8096",
                "--media-server-token",
                "secret-token",
                "--media-server-max-retries",
                "1",
                "--mode",
                "copy",
            ],
        )
        assert result.exit_code == 0
        assert mock_open.call_count == 1

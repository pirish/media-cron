import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from media_cron.config import GeneralConfig, MediaCronConfig, PathsConfig, VideoConfig
from media_cron.metadata.models import MediaServerConfig, VideoWorkflowMode
from media_cron.pipeline import Pipeline


def test_debounced_media_server_notification_on_batch_success(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "destination"
    dest_dir.mkdir()

    # Create 2 video files in staging
    v1 = staging_dir / "Severance.S01E01.1080p.mkv"
    v1.write_bytes(b"\x1a\x45\xdf\xa3" + b"video1" * 100)
    v2 = staging_dir / "Severance.S01E02.1080p.mkv"
    v2.write_bytes(b"\x1a\x45\xdf\xa3" + b"video2" * 100)

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir, staging_dir=staging_dir, destination_dir=dest_dir
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.DIRECT,
            media_server=MediaServerConfig(
                enabled=True,
                provider="jellyfin",
                url="http://jellyfin.local:8096",
                token="test-token",
            ),
        ),
    )

    pipeline = Pipeline(config=cfg)

    # Mock urllib.request.urlopen
    mock_resp = MagicMock()
    mock_resp.status = 204
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        summary = pipeline.run()

        # Both files organized
        assert summary.exit_code == 0
        assert summary.processed_count == 2

        # Debounced: Exactly 1 rescan call dispatched for the entire batch
        assert mock_urlopen.call_count == 1

        assert summary.video_summary is not None
        assert summary.video_summary.get("rescan_notifications_sent") == 1
        assert summary.video_summary.get("rescan_errors") == 0


def test_media_server_offline_non_blocking_error_handling(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "destination"
    dest_dir.mkdir()

    v1 = staging_dir / "Dune.Part.Two.2024.2160p.mkv"
    v1.write_bytes(b"\x1a\x45\xdf\xa3" + b"dune" * 100)

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir, staging_dir=staging_dir, destination_dir=dest_dir
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.DIRECT,
            media_server=MediaServerConfig(
                enabled=True,
                provider="plex",
                url="http://offline-plex:32400",
                token="plex-token",
                max_retries=0,
            ),
        ),
    )

    pipeline = Pipeline(config=cfg)

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        summary = pipeline.run()

        # Pipeline must succeed (exit code 0) even if media server rescan fails
        assert summary.exit_code == 0
        assert summary.processed_count == 1

        # File is still properly organized
        expected_file = (
            dest_dir / "Movies" / "Dune Part Two (2024)" / "Dune Part Two (2024) [2160p].mkv"
        )
        assert expected_file.exists()

        # Telemetry records rescan failure without aborting batch
        assert summary.video_summary is not None
        assert summary.video_summary.get("rescan_notifications_sent") == 0
        assert summary.video_summary.get("rescan_errors") == 1

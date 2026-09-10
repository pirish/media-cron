from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.config import GeneralConfig, MediaCronConfig, PathsConfig, VideoConfig
from media_cron.metadata.models import MediaServerConfig, VideoWorkflowMode
from media_cron.pipeline import Pipeline

runner = CliRunner()


def test_quickstart_scenario_1_spool_release_handoff(tmp_path: Path):
    """Scenario 1: Release bundle drop-folder spooling with companion preservation and post-command."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    spool_dir = tmp_path / "video_drop"
    spool_dir.mkdir()

    rel_dir = source_dir / "Severance.S01E01.1080p"
    rel_dir.mkdir()
    (rel_dir / "Severance.S01E01.1080p.mkv").write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 100)
    (rel_dir / "Severance.S01E01.1080p.en.forced.srt").write_text("1\n00:00:01 --> 00:00:04\nSub")
    (rel_dir / "poster.jpg").write_bytes(b"poster image data")
    (rel_dir / "release.nfo").write_text("info")

    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            str(source_dir),
            "--staging",
            str(staging_dir),
            "--video-spool-dir",
            str(spool_dir),
            "--video-post-command",
            "echo 'Spooled {release_path}'",
            "--mode",
            "copy",
            "--format",
            "text",
        ],
    )
    assert result.exit_code == 0
    target_rel = spool_dir / "Severance.S01E01.1080p"
    assert target_rel.exists()
    assert (target_rel / "Severance.S01E01.1080p.mkv").exists()
    assert (target_rel / "Severance.S01E01.1080p.en.forced.srt").exists()
    assert (target_rel / "poster.jpg").exists()
    assert (target_rel / "release.nfo").exists()
    assert not any(p.name.startswith(".incoming_") for p in spool_dir.iterdir())


def test_quickstart_scenario_2_direct_library_organization(tmp_path: Path):
    """Scenario 2: Autonomous direct movie & TV organization with companion subtitles."""
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "media_library"
    dest_dir.mkdir()

    # Movie + Subtitle
    movie_rel = staging_dir / "Dune.Part.Two.2024.2160p"
    movie_rel.mkdir()
    (movie_rel / "Dune.Part.Two.2024.2160p.mkv").write_bytes(b"\x1a\x45\xdf\xa3" + b"dune" * 100)
    (movie_rel / "Dune.Part.Two.2024.2160p.en.srt").write_text("1\n00:00:01 --> 00:00:04\nSub")

    # TV Episode + Subtitle
    (staging_dir / "Succession.S04E01.The.Munsters.1080p.mkv").write_bytes(
        b"\x1a\x45\xdf\xa3" + b"tv" * 100
    )
    (staging_dir / "Succession.S04E01.The.Munsters.1080p.en.srt").write_text(
        "1\n00:00:01 --> 00:00:04\nSub"
    )

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir, staging_dir=staging_dir, destination_dir=dest_dir
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.DIRECT,
            preserve_companions=True,
        ),
    )
    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    assert summary.exit_code == 0
    # Movie verification
    movie_folder = dest_dir / "Movies" / "Dune Part Two (2024)"
    assert movie_folder.exists()
    assert (movie_folder / "Dune Part Two (2024) [2160p].mkv").exists()
    assert (movie_folder / "Dune Part Two (2024) [2160p].en.srt").exists()

    # TV verification
    tv_folder = dest_dir / "TV" / "Succession" / "Season 04"
    assert tv_folder.exists()
    assert (tv_folder / "Succession - S04E01 - The Munsters [1080p].mkv").exists()
    assert (tv_folder / "Succession - S04E01 - The Munsters [1080p].en.srt").exists()


def test_quickstart_scenario_3_quality_aware_collision_upgrade(tmp_path: Path):
    """Scenario 3: Quality-aware destination collision upgrade (2160p replaces 1080p)."""
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "media_library"
    dest_dir.mkdir()

    # Pre-existing 1080p movie in destination
    movie_folder = dest_dir / "Movies" / "Inception (2010)"
    movie_folder.mkdir(parents=True)
    existing_file = movie_folder / "Inception (2010) [1080p].mkv"
    existing_file.write_bytes(b"old 1080p movie")

    # Incoming 2160p higher quality upgrade
    incoming_file = staging_dir / "Inception.2010.2160p.UHD.mkv"
    incoming_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"new 4k inception" * 100)

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir, staging_dir=staging_dir, destination_dir=dest_dir
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.DIRECT,
        ),
    )
    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    assert summary.exit_code == 0
    # Old file replaced by higher-quality upgrade
    upgraded_file = movie_folder / "Inception (2010) [2160p].mkv"
    assert upgraded_file.exists()
    assert not existing_file.exists()


def test_quickstart_scenario_4_debounced_media_server_rescan(tmp_path: Path):
    """Scenario 4: Debounced media server rescan notification with non-blocking error tolerance."""
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "media_library"
    dest_dir.mkdir()

    # 2 TV episodes organized in one batch
    (staging_dir / "Dark.S01E01.1080p.mkv").write_bytes(b"\x1a\x45\xdf\xa3" + b"ep1" * 100)
    (staging_dir / "Dark.S01E02.1080p.mkv").write_bytes(b"\x1a\x45\xdf\xa3" + b"ep2" * 100)

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
                token="auth-token",
            ),
        ),
    )

    mock_resp = MagicMock()
    mock_resp.status = 204
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        pipeline = Pipeline(config=cfg)
        summary = pipeline.run()

        assert summary.exit_code == 0
        assert summary.processed_count == 2
        # Debounced: Exactly 1 rescan notification dispatched for the multi-file batch
        assert mock_open.call_count == 1
        assert summary.video_summary.get("rescan_notifications_sent") == 1


def test_quickstart_scenario_5_predictive_dry_run_simulation(tmp_path: Path):
    """Scenario 5: 100% predictive dry-run simulation without disk writes or remote calls."""
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "media_library"
    dest_dir.mkdir()

    (staging_dir / "Gladiator.2000.1080p.mkv").write_bytes(b"\x1a\x45\xdf\xa3" + b"gladiator" * 100)
    (staging_dir / "Gladiator.2000.1080p.en.srt").write_text("1\n00:00:01 --> 00:00:04\nSub")

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir, staging_dir=staging_dir, destination_dir=dest_dir
        ),
        general=GeneralConfig(mode="copy", dry_run=True),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.DIRECT,
            media_server=MediaServerConfig(
                enabled=True,
                provider="plex",
                url="http://plex.local:32400",
                token="plex-token",
            ),
        ),
    )

    with patch("urllib.request.urlopen") as mock_open:
        pipeline = Pipeline(config=cfg)
        summary = pipeline.run()

        assert summary.exit_code == 0
        assert summary.dry_run is True
        # Zero disk modifications
        assert not (dest_dir / "Movies" / "Gladiator (2000)").exists()
        # Zero remote network calls
        mock_open.assert_not_called()
        # Accurate planned actions reported
        assert summary.processed_count >= 1
        assert summary.video_summary is not None

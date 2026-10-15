from pathlib import Path

from media_cron.config import (
    GeneralConfig,
    MediaCronConfig,
    PathsConfig,
    VideoConfig,
)
from media_cron.pipeline import Pipeline


def test_pipeline_stages_unrecognized_items(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    review_dir = tmp_path / "review"
    review_dir.mkdir()

    # Recognizable movie
    rec_file = staging_dir / "Inception.2010.1080p.mkv"
    rec_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    # Unrecognizable file
    unrec_file = staging_dir / "Mystery_File_123.dat"
    unrec_file.write_bytes(b"some unknown binary data" * 50)

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
            review_dir=review_dir,
        ),
        general=GeneralConfig(mode="move", dry_run=False),
        video=VideoConfig(enabled=True, workflow_mode="direct"),
    )

    pipeline = Pipeline(cfg)
    summary = pipeline.run()

    # Recognizable movie was organized
    assert not rec_file.exists()
    assert (dest_dir / "Movies" / "Inception (2010)" / "Inception (2010) [1080p].mkv").exists()

    # Unrecognizable file was moved to review_dir
    assert not unrec_file.exists()
    review_items = [d for d in review_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    assert len(review_items) == 1
    item_dir = review_items[0]
    assert (item_dir / "Mystery_File_123.dat").exists()
    assert (item_dir / "manifest.json").exists()

    # Telemetry in summary
    assert summary.unrecognized_count >= 1
    assert summary.review_staged_count >= 1


def test_pipeline_unrecognized_without_review_dir(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    unrec_file = staging_dir / "Unconfigured_Review.xyz"
    unrec_file.write_bytes(b"data" * 10)

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
            review_dir=None,  # Not configured
        ),
        general=GeneralConfig(mode="move", dry_run=False),
    )

    pipeline = Pipeline(cfg)
    summary = pipeline.run()

    # Remains in staging untouched
    assert unrec_file.exists()
    assert summary.unrecognized_count >= 1
    assert summary.review_staged_count == 0


def test_pipeline_unrecognized_with_torrent_plugin(tmp_path: Path):
    """Verify that pipeline handles unrecognized staging when torrents with TorrentFile objects are active."""
    from media_cron.torrent.models import TorrentFile, TorrentItem, TorrentState

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()

    unrec_file = staging_dir / "Unknown_Payload.iso"
    unrec_file.write_bytes(b"data" * 50)

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
            review_dir=review_dir,
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
    )

    pipeline = Pipeline(cfg)

    class DummyConfig:
        def __init__(self):
            from media_cron.torrent.models import TorrentSeedingConfig

            self.seeding = TorrentSeedingConfig(mode="none")

        def translate_path(self, p):
            return Path(p)

    class MockClient:
        def relocate_storage(self, info_hash, destination):
            return True

        def apply_completion_state(self, info_hash, tag, category, pause=False):
            return True

    class DummyTorrentPlugin:
        def __init__(self):
            self.plugin_name = "torrent"
            self.config = DummyConfig()
            self.client = MockClient()
            self.processed_torrents = [
                TorrentItem(
                    info_hash="abc12345",
                    name="Movie.2024",
                    total_size=1024 * 1024,
                    progress=1.0,
                    state=TorrentState.SEEDING,
                    save_path=str(seed_dir),
                    content_path=str(seed_dir / "Movie.2024.mkv"),
                    files=[
                        TorrentFile(name="Movie.2024.mkv", size=1024 * 1024),
                    ],
                )
            ]

        def discover(self, source, staging, dry_run=False):
            return []

    dummy = DummyTorrentPlugin()
    pipeline._get_input_plugins = lambda: ([], dummy)

    summary = pipeline.run()
    assert summary.exit_code == 0
    assert summary.unrecognized_count >= 1
    assert summary.review_staged_count >= 1

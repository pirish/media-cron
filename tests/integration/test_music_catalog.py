from pathlib import Path
from unittest.mock import MagicMock, patch

from media_cron.config import (
    GeneralConfig,
    MediaCronConfig,
    MetadataCacheConfig,
    MusicConfig,
    PathsConfig,
)
from media_cron.metadata.base import ProviderUnavailableError
from media_cron.metadata.models import MusicCatalogMatch, MusicWorkflowMode
from media_cron.pipeline import Pipeline


def test_music_catalog_pipeline_enrichment(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "library"
    dest_dir.mkdir()
    cache_file = tmp_path / "cache" / "music_cache.json"

    album_dir = staging_dir / "Animals"
    album_dir.mkdir()
    t1 = album_dir / "01 - Dogs.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)

    # Local tags have artist and title, but missing year
    mock_tag = MagicMock(
        title="Dogs",
        artist="Pink Floyd",
        album="Animals",
        albumartist=None,
        track=1,
        disc=1,
        year=None,
        genre=None,
    )

    catalog_match = MusicCatalogMatch(
        title="Animals",
        artist="Pink Floyd",
        release_id="mb-rel-777",
        provider="musicbrainz",
        confidence=0.96,
        year=1977,
        track_count=5,
        tracks=["Pigs on the Wing 1", "Dogs", "Pigs", "Sheep", "Pigs on the Wing 2"],
    )

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        music=MusicConfig(
            enabled=True,
            workflow_mode=MusicWorkflowMode.DIRECT,
            enable_external_lookup=True,
            confidence_threshold=0.85,
            cache=MetadataCacheConfig(cache_file=cache_file),
        ),
    )

    with (
        patch("media_cron.metadata.music_reader.TinyTag.get", return_value=mock_tag),
        patch(
            "media_cron.metadata.providers.musicbrainz.MusicBrainzProvider.search_release",
            return_value=[catalog_match],
        ),
    ):
        pipeline = Pipeline(config=cfg)
        summary = pipeline.run()

        assert summary.exit_code == 0
        assert summary.music_summary is not None
        assert summary.music_summary.get("external_matches", 0) >= 1

        # Canonical year 1977 from catalog should appear in library path
        target_album_dir = dest_dir / "Music" / "Pink Floyd" / "Animals (1977)"
        assert target_album_dir.exists()
        assert (target_album_dir / "01 - Dogs.flac").exists()
        assert cache_file.exists()


def test_music_catalog_offline_fallback(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "library"
    dest_dir.mkdir()

    album_dir = staging_dir / "Animals"
    album_dir.mkdir()
    t1 = album_dir / "01 - Dogs.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)

    mock_tag = MagicMock(
        title="Dogs",
        artist="Pink Floyd",
        album="Animals",
        albumartist="Pink Floyd",
        track=1,
        disc=1,
        year=1977,
        genre="Rock",
    )

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        music=MusicConfig(
            enabled=True,
            workflow_mode=MusicWorkflowMode.DIRECT,
            enable_external_lookup=True,
        ),
    )

    with (
        patch("media_cron.metadata.music_reader.TinyTag.get", return_value=mock_tag),
        patch(
            "media_cron.metadata.providers.musicbrainz.MusicBrainzProvider.search_release",
            side_effect=ProviderUnavailableError("Offline"),
        ),
    ):
        pipeline = Pipeline(config=cfg)
        summary = pipeline.run()

        # Should fall back cleanly without failing
        assert summary.exit_code == 0
        target_album_dir = dest_dir / "Music" / "Pink Floyd" / "Animals (1977)"
        assert target_album_dir.exists()

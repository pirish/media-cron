from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from media_cron.config import (
    AudiobookConfig,
    ExternalProviderConfig,
    GeneralConfig,
    MediaCronConfig,
    PathsConfig,
)
from media_cron.metadata.aggregator import AudiobookBundleAggregator
from media_cron.metadata.base import MetadataProviderRegistry
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.identifier import AudiobookIdentifier
from media_cron.metadata.models import MetadataMatch
from media_cron.pipeline import Pipeline
from media_cron.plugins.input.directory import DirectoryScannerInput
from media_cron.plugins.lookup.audio import AudioTagLookup
from media_cron.plugins.output.cleaner import JunkCleanerOutput
from media_cron.plugins.output.organizer import LibraryOrganizerOutput
from media_cron.plugins.registry import PluginRegistry


@pytest.fixture
def isolated_env(tmp_path: Path):
    source = tmp_path / "source"
    staging = tmp_path / "staging"
    dest = tmp_path / "destination"
    cache = tmp_path / "cache"

    source.mkdir()
    staging.mkdir()
    dest.mkdir()
    cache.mkdir()

    return {
        "source": source,
        "staging": staging,
        "dest": dest,
        "cache": cache,
    }


def test_multi_file_bundle_with_disc_subfolders_and_album_consensus(isolated_env):
    source = isolated_env["source"]
    staging = isolated_env["staging"]
    dest = isolated_env["dest"]
    cache_file = isolated_env["cache"] / "audiobook_cache.json"

    # Create multi-file directory with CD1 and CD2 inside Audiobooks
    book_folder = source / "Audiobooks" / "Unsorted Kings"
    cd1 = book_folder / "CD1"
    cd2 = book_folder / "CD2"
    cd1.mkdir(parents=True)
    cd2.mkdir(parents=True)

    t1 = cd1 / "01 - Track 1.mp3"
    t2 = cd1 / "02 - Track 2.mp3"
    t3 = cd2 / "03 - Track 3.mp3"
    for t in (t1, t2, t3):
        t.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 50)

    # Provider mock
    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="The Way of Kings",
            author="Brandon Sanderson",
            year=2010,
            work_id="OL15359239W",
            provider="openlibrary",
            confidence=0.97,
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: mock_provider)

    cache = MetadataCache(cache_file=cache_file)
    audiobook_config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )
    identifier = AudiobookIdentifier(config=audiobook_config, registry=registry, cache=cache)
    aggregator = AudiobookBundleAggregator(identifier=identifier)

    # Mock TinyTag album consensus
    mock_tag = MagicMock(
        album="The Way of Kings",
        artist="Brandon Sanderson",
        genre="Audiobook",
        track=None,
        year=None,
        bitrate=None,
    )
    with (
        patch("media_cron.metadata.aggregator.TinyTag") as mock_tt_agg,
        patch("media_cron.plugins.lookup.audio.TinyTag") as mock_tt_lookup,
    ):
        mock_tt_agg.get.return_value = mock_tag
        mock_tt_lookup.get.return_value = mock_tag

        plugin_registry = PluginRegistry()
        plugin_registry.register_lookup(
            "audio_tag", lambda: AudioTagLookup(identifier=identifier, aggregator=aggregator)
        )
        plugin_registry.register_input("directory_scanner", DirectoryScannerInput)
        plugin_registry.register_output("library_organizer", LibraryOrganizerOutput)
        plugin_registry.register_output("junk_cleaner", JunkCleanerOutput)

        config = MediaCronConfig(
            paths=PathsConfig(source_dir=source, staging_dir=staging, destination_dir=dest),
            general=GeneralConfig(mode="copy", dry_run=False),
            audiobook=audiobook_config,
        )

        pipeline = Pipeline(config=config, registry=plugin_registry)
        summary = pipeline.run()

        assert summary.error_count == 0
        assert summary.processed_count == 3
        # Provider must only be called ONCE for the entire bundle of 3 tracks!
        assert mock_provider.search.call_count == 1

        # Check destination organized files
        expected_dir = dest / "Audiobooks" / "Brandon Sanderson" / "The Way of Kings"
        assert (expected_dir / "01 - The Way of Kings.mp3").exists()
        assert (expected_dir / "02 - The Way of Kings.mp3").exists()
        assert (expected_dir / "03 - The Way of Kings.mp3").exists()


def test_multi_file_bundle_stripped_tags_fallback_to_parent_folder(isolated_env):
    source = isolated_env["source"]
    staging = isolated_env["staging"]
    dest = isolated_env["dest"]
    cache_file = isolated_env["cache"] / "audiobook_cache.json"

    # Multi-file directory named "Author - Title" in Audiobooks
    book_folder = source / "Audiobooks" / "Frank Herbert - Children of Dune"
    book_folder.mkdir(parents=True)

    t1 = book_folder / "01 - Part 1.mp3"
    t2 = book_folder / "02 - Part 2.mp3"
    t1.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 50)
    t2.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 50)

    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="Children of Dune",
            author="Frank Herbert",
            year=1976,
            provider="openlibrary",
            confidence=0.98,
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: mock_provider)

    cache = MetadataCache(cache_file=cache_file)
    audiobook_config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )
    identifier = AudiobookIdentifier(config=audiobook_config, registry=registry, cache=cache)
    aggregator = AudiobookBundleAggregator(identifier=identifier)

    # Empty tags simulate missing/stripped tags
    mock_empty = MagicMock(
        album=None,
        artist=None,
        genre=None,
        track=None,
        year=None,
        bitrate=None,
    )
    with (
        patch("media_cron.metadata.aggregator.TinyTag") as mock_tt_agg,
        patch("media_cron.plugins.lookup.audio.TinyTag") as mock_tt_lookup,
    ):
        mock_tt_agg.get.return_value = mock_empty
        mock_tt_lookup.get.return_value = mock_empty

        plugin_registry = PluginRegistry()
        plugin_registry.register_lookup(
            "audio_tag", lambda: AudioTagLookup(identifier=identifier, aggregator=aggregator)
        )
        plugin_registry.register_input("directory_scanner", DirectoryScannerInput)
        plugin_registry.register_output("library_organizer", LibraryOrganizerOutput)
        plugin_registry.register_output("junk_cleaner", JunkCleanerOutput)

        config = MediaCronConfig(
            paths=PathsConfig(source_dir=source, staging_dir=staging, destination_dir=dest),
            general=GeneralConfig(mode="copy", dry_run=False),
            audiobook=audiobook_config,
        )

        pipeline = Pipeline(config=config, registry=plugin_registry)
        summary = pipeline.run()

        assert summary.error_count == 0
        assert summary.processed_count == 2
        assert mock_provider.search.call_count == 1

        expected_dir = dest / "Audiobooks" / "Frank Herbert" / "Children of Dune"
        assert (expected_dir / "01 - Children of Dune.mp3").exists()
        assert (expected_dir / "02 - Children of Dune.mp3").exists()

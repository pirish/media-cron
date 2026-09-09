from pathlib import Path
from unittest.mock import MagicMock

import pytest

from media_cron.config import (
    AudiobookConfig,
    ExternalProviderConfig,
    GeneralConfig,
    MediaCronConfig,
    PathsConfig,
)
from media_cron.metadata.base import MetadataProviderRegistry, ProviderUnavailableError
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.identifier import AudiobookIdentifier
from media_cron.metadata.models import MetadataMatch
from media_cron.pipeline import Pipeline
from media_cron.plugins.lookup.audio import AudioTagLookup
from media_cron.plugins.registry import PluginRegistry


@pytest.fixture
def isolated_env(tmp_path: Path):
    source_dir = tmp_path / "source"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "destination"
    cache_dir = tmp_path / "cache"

    source_dir.mkdir()
    staging_dir.mkdir()
    dest_dir.mkdir()
    cache_dir.mkdir()

    return {
        "source": source_dir,
        "staging": staging_dir,
        "dest": dest_dir,
        "cache": cache_dir,
    }


def test_single_file_m4b_audiobook_pipeline_ingestion(isolated_env):
    source = isolated_env["source"]
    staging = isolated_env["staging"]
    dest = isolated_env["dest"]
    cache_file = isolated_env["cache"] / "audiobook_cache.json"

    # Create dummy .m4b audiobook file with valid MP4 container atom
    audiobook_file = source / "The Hobbit.m4b"
    audiobook_file.write_bytes(
        b"\x00\x00\x00\x1cftypM4B \x00\x00\x00\x00M4B mp42isom" + b"\x00" * 100
    )

    # Mock provider returning confident match
    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="The Hobbit",
            author="J.R.R. Tolkien",
            year=1937,
            work_id="OL262758W",
            provider="openlibrary",
            confidence=0.96,
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

    plugin_registry = PluginRegistry()
    plugin_registry.register_lookup("audio_tag", lambda: AudioTagLookup(identifier=identifier))
    # Register default input & output plugins
    from media_cron.plugins.input.directory import DirectoryScannerInput
    from media_cron.plugins.output.cleaner import JunkCleanerOutput
    from media_cron.plugins.output.organizer import LibraryOrganizerOutput

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

    assert summary.total_scanned == 1
    assert summary.processed_count == 1
    assert summary.error_count == 0

    # Verify destination structure: Audiobooks/{author}/{title}/{track:02d} - {title}.{ext}
    expected_dest = dest / "Audiobooks" / "J.R.R. Tolkien" / "The Hobbit" / "01 - The Hobbit.m4b"
    assert expected_dest.exists()
    assert expected_dest.stat().st_size > 0

    # Verify telemetry in identifier
    ident_summary = identifier.get_summary()
    assert ident_summary["total_audiobooks"] == 1
    assert ident_summary["identified_external"] == 1
    assert ident_summary["average_confidence"] == 0.96


def test_single_file_mp3_with_audiobook_path_hint(isolated_env):
    source = isolated_env["source"]
    staging = isolated_env["staging"]
    dest = isolated_env["dest"]
    cache_file = isolated_env["cache"] / "audiobook_cache.json"

    # Create .mp3 in an audiobooks subfolder
    ab_dir = source / "Audiobooks"
    ab_dir.mkdir()
    mp3_file = ab_dir / "Frank Herbert - Dune.mp3"
    mp3_file.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 100)

    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="Dune",
            author="Frank Herbert",
            year=1965,
            work_id="OL893415W",
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

    plugin_registry = PluginRegistry()
    plugin_registry.register_lookup("audio_tag", lambda: AudioTagLookup(identifier=identifier))
    from media_cron.plugins.input.directory import DirectoryScannerInput
    from media_cron.plugins.output.cleaner import JunkCleanerOutput
    from media_cron.plugins.output.organizer import LibraryOrganizerOutput

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

    assert summary.processed_count == 1
    expected_dest = dest / "Audiobooks" / "Frank Herbert" / "Dune" / "01 - Dune.mp3"
    assert expected_dest.exists()


def test_single_file_offline_graceful_fallback(isolated_env):
    source = isolated_env["source"]
    staging = isolated_env["staging"]
    dest = isolated_env["dest"]
    cache_file = isolated_env["cache"] / "audiobook_cache.json"

    audiobook_file = source / "Neil Gaiman - Neverwhere.m4b"
    audiobook_file.write_bytes(
        b"\x00\x00\x00\x1cftypM4B \x00\x00\x00\x00M4B mp42isom" + b"\x00" * 100
    )

    # Simulate network outage / DNS failure
    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.side_effect = ProviderUnavailableError("Network is unreachable")

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

    plugin_registry = PluginRegistry()
    plugin_registry.register_lookup("audio_tag", lambda: AudioTagLookup(identifier=identifier))
    from media_cron.plugins.input.directory import DirectoryScannerInput
    from media_cron.plugins.output.cleaner import JunkCleanerOutput
    from media_cron.plugins.output.organizer import LibraryOrganizerOutput

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

    # Pipeline does not crash, fallback to filename
    assert summary.error_count == 0
    assert summary.processed_count == 1
    expected_dest = dest / "Audiobooks" / "Neil Gaiman" / "Neverwhere" / "01 - Neverwhere.m4b"
    assert expected_dest.exists()

    ident_summary = identifier.get_summary()
    assert ident_summary["identified_local_only"] == 1
    assert ident_summary["identified_external"] == 0

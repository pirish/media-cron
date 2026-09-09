import time
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


def test_multi_provider_cascade_integration(isolated_env):
    source = isolated_env["source"]
    staging = isolated_env["staging"]
    dest = isolated_env["dest"]
    cache_file = isolated_env["cache"] / "audiobook_cache.json"

    # Create dummy .m4b
    ab_file = source / "The Way of Kings.m4b"
    ab_file.write_bytes(b"\x00\x00\x00\x1cftypM4B \x00\x00\x00\x00M4B mp42isom" + b"\x00" * 100)

    # Primary provider (openlibrary) returns candidate below 0.85
    mock_ol = MagicMock()
    mock_ol.provider_name = "openlibrary"
    mock_ol.search.return_value = [
        MetadataMatch(
            title="The Way of Kings (Preview)",
            author="Unknown",
            provider="openlibrary",
            confidence=0.55,
        )
    ]

    # Secondary provider (audnexus) returns confident match with narrator and series
    mock_aud = MagicMock()
    mock_aud.provider_name = "audnexus"
    mock_aud.search.return_value = [
        MetadataMatch(
            title="The Way of Kings",
            author="Brandon Sanderson",
            year=2010,
            narrator="Michael Kramer, Kate Reading",
            series="The Stormlight Archive",
            volume="1",
            work_id="B002V1OF70",
            provider="audnexus",
            confidence=0.96,
        )
    ]

    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: mock_ol)
    registry.register("audnexus", lambda **kw: mock_aud)

    cache = MetadataCache(cache_file=cache_file)
    audiobook_config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            ),
            "audnexus": ExternalProviderConfig(provider_name="audnexus", enabled=True, priority=20),
        },
    )
    identifier = AudiobookIdentifier(config=audiobook_config, registry=registry, cache=cache)

    plugin_registry = PluginRegistry()
    plugin_registry.register_lookup("audio_tag", lambda: AudioTagLookup(identifier=identifier))
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
    assert summary.processed_count == 1

    # Audnexus was used because Open Library had low confidence
    assert mock_ol.search.call_count == 1
    assert mock_aud.search.call_count == 1

    expected_dest = (
        dest / "Audiobooks" / "Brandon Sanderson" / "The Way of Kings" / "01 - The Way of Kings.m4b"
    )
    assert expected_dest.exists()

    ident_summary = identifier.get_summary()
    assert ident_summary["provider_breakdown"]["audnexus"] == 1


def test_provider_rate_limit_enforcement(tmp_path: Path):
    mock_provider = MagicMock()
    mock_provider.provider_name = "audnexus"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="Book",
            author="Author",
            provider="audnexus",
            confidence=0.90,
        )
    ]

    registry = MetadataProviderRegistry()
    registry.register("audnexus", lambda **kw: mock_provider)

    # 0.2s delay
    from media_cron.config import MetadataCacheConfig

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        cache=MetadataCacheConfig(enabled=False),
        providers={
            "audnexus": ExternalProviderConfig(
                provider_name="audnexus",
                enabled=True,
                priority=10,
                rate_limit_delay=0.15,
            )
        },
    )
    identifier = AudiobookIdentifier(config=config, registry=registry, cache=None)

    start = time.time()
    identifier.identify(title="Book 1", author="Author", has_local_tags=True)
    identifier.identify(title="Book 2", author="Author", has_local_tags=True)
    elapsed = time.time() - start

    # Two requests with 0.15s delay should take at least 0.15s
    assert elapsed >= 0.14

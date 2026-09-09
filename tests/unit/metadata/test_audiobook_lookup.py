from pathlib import Path
from unittest.mock import MagicMock

import pytest

from media_cron.config import AudiobookConfig, ExternalProviderConfig
from media_cron.metadata.base import (
    MetadataProviderRegistry,
    ProviderTimeoutError,
)
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.identifier import AudiobookIdentifier
from media_cron.metadata.models import MetadataMatch


@pytest.fixture
def mock_cache(tmp_path: Path) -> MetadataCache:
    cache_file = tmp_path / "cache" / "test_cache.json"
    return MetadataCache(cache_file=cache_file, default_ttl=3600)


@pytest.fixture
def mock_registry() -> MetadataProviderRegistry:
    registry = MetadataProviderRegistry()
    return registry


def test_audiobook_identification_with_confident_external_match(
    mock_cache: MetadataCache, mock_registry: MetadataProviderRegistry
):
    # Setup mock provider
    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="The Fellowship of the Ring",
            author="J.R.R. Tolkien",
            year=1954,
            work_id="OL27479W",
            provider="openlibrary",
            confidence=0.95,
        )
    ]
    mock_registry.register("openlibrary", lambda **kw: mock_provider)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=mock_registry, cache=mock_cache)
    result = identifier.identify(
        title="Fellowship of the Ring",
        author="J. R. R. Tolkien",
        has_local_tags=True,
    )

    assert result.title == "The Fellowship of the Ring"
    assert result.author == "J.R.R. Tolkien"
    assert result.year == 1954
    assert result.provider == "openlibrary"
    assert result.confidence == 0.95

    summary = identifier.get_summary()
    assert summary["total_audiobooks"] == 1
    assert summary["identified_external"] == 1
    assert summary["identified_local_only"] == 0
    assert summary["cache_misses"] == 1
    assert summary["provider_breakdown"]["openlibrary"] == 1


def test_audiobook_identification_offline_or_error_fallback(
    mock_cache: MetadataCache, mock_registry: MetadataProviderRegistry
):
    # Provider raises timeout
    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.side_effect = ProviderTimeoutError("Request timed out")
    mock_registry.register("openlibrary", lambda **kw: mock_provider)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=mock_registry, cache=mock_cache)

    # 1. Fallback with local tags
    result_tags = identifier.identify(
        title="Local Book Title",
        author="Local Author",
        has_local_tags=True,
    )
    assert result_tags.title == "Local Book Title"
    assert result_tags.author == "Local Author"
    assert result_tags.provider == "local_tag"
    assert result_tags.confidence == 0.75

    # 2. Fallback with filename only
    result_fn = identifier.identify(
        title="Filename Title",
        author="Filename Author",
        has_local_tags=False,
    )
    assert result_fn.title == "Filename Title"
    assert result_fn.author == "Filename Author"
    assert result_fn.provider == "filename"
    assert result_fn.confidence == 0.50

    summary = identifier.get_summary()
    assert summary["total_audiobooks"] == 2
    assert summary["identified_local_only"] == 2
    assert summary["identified_external"] == 0


def test_audiobook_identification_disabled_external_lookup(
    mock_cache: MetadataCache, mock_registry: MetadataProviderRegistry
):
    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_registry.register("openlibrary", lambda **kw: mock_provider)

    config = AudiobookConfig(enable_external_lookup=False)
    identifier = AudiobookIdentifier(config=config, registry=mock_registry, cache=mock_cache)

    result = identifier.identify(
        title="Offline Book",
        author="Offline Author",
        has_local_tags=True,
    )

    mock_provider.search.assert_not_called()
    assert result.title == "Offline Book"
    assert result.author == "Offline Author"
    assert result.provider == "local_tag"
    assert result.confidence == 0.75

    summary = identifier.get_summary()
    assert summary["total_audiobooks"] == 1
    assert summary["identified_local_only"] == 1


def test_audiobook_identification_cache_hit(
    mock_cache: MetadataCache, mock_registry: MetadataProviderRegistry
):
    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="Dune",
            author="Frank Herbert",
            provider="openlibrary",
            confidence=0.98,
        )
    ]
    mock_registry.register("openlibrary", lambda **kw: mock_provider)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=mock_registry, cache=mock_cache)

    # First lookup: cache miss, calls provider
    res1 = identifier.identify(title="Dune", author="Frank Herbert", has_local_tags=True)
    assert res1.confidence == 0.98
    assert mock_provider.search.call_count == 1

    # Second lookup: cache hit, does NOT call provider
    res2 = identifier.identify(title="Dune", author="Frank Herbert", has_local_tags=True)
    assert res2.confidence == 0.98
    assert mock_provider.search.call_count == 1

    summary = identifier.get_summary()
    assert summary["total_audiobooks"] == 2
    assert summary["cache_hits"] == 1
    assert summary["cache_misses"] == 1


def test_audiobook_identification_filename_parsing(
    mock_cache: MetadataCache, mock_registry: MetadataProviderRegistry
):
    config = AudiobookConfig(enable_external_lookup=False)
    identifier = AudiobookIdentifier(config=config, registry=mock_registry, cache=mock_cache)

    title, author = identifier.parse_filename("01 - Brandon Sanderson - Mistborn")
    assert title == "Mistborn"
    assert author == "Brandon Sanderson"

    title2, author2 = identifier.parse_filename("Neil Gaiman - Neverwhere")
    assert title2 == "Neverwhere"
    assert author2 == "Neil Gaiman"

    title3, author3 = identifier.parse_filename("Just A Title")
    assert title3 == "Just A Title"
    assert author3 is None


def test_audiobook_identification_partial_enrichment_below_threshold(
    mock_cache: MetadataCache, mock_registry: MetadataProviderRegistry
):
    # External match has confidence 0.72 (below 0.85 threshold, but >= 0.60)
    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="Slightly Different Title",
            author="Different Author Variant",
            year=1999,
            narrator="Famous Narrator",
            series="Epic Series",
            volume="1",
            provider="openlibrary",
            confidence=0.72,
        )
    ]
    mock_registry.register("openlibrary", lambda **kw: mock_provider)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=mock_registry, cache=mock_cache)
    result = identifier.identify(
        title="Original Title",
        author="Original Author",
        has_local_tags=True,
    )

    # Local title and author preserved!
    assert result.title == "Original Title"
    assert result.author == "Original Author"
    # Secondary fields enriched from external match!
    assert result.narrator == "Famous Narrator"
    assert result.series == "Epic Series"
    assert result.volume == "1"
    assert result.year == 1999
    assert result.provider == "local_tag"
    assert result.confidence == 0.75

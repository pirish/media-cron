from pathlib import Path
from unittest.mock import MagicMock

import pytest

from media_cron.config import AudiobookConfig, ExternalProviderConfig
from media_cron.metadata.base import MetadataProviderRegistry
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.identifier import AudiobookIdentifier
from media_cron.metadata.models import MetadataMatch


@pytest.fixture
def mock_cache(tmp_path: Path) -> MetadataCache:
    return MetadataCache(cache_file=tmp_path / "cache.json")


def test_confidence_above_threshold_overrides_local(mock_cache: MetadataCache):
    provider = MagicMock()
    provider.provider_name = "openlibrary"
    provider.search.return_value = [
        MetadataMatch(
            title="Dune (Canonical)",
            author="Frank Herbert (Canonical)",
            year=1965,
            provider="openlibrary",
            confidence=0.88,
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: provider)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=registry, cache=mock_cache)
    result = identifier.identify(
        title="Dune (Messy)",
        author="Frank Herbert (Messy)",
        has_local_tags=True,
    )

    assert result.title == "Dune (Canonical)"
    assert result.author == "Frank Herbert (Canonical)"
    assert result.provider == "openlibrary"
    assert result.confidence == 0.88


def test_confidence_below_threshold_preserves_local_author_and_title(mock_cache: MetadataCache):
    provider = MagicMock()
    provider.provider_name = "openlibrary"
    provider.search.return_value = [
        MetadataMatch(
            title="Dune (Alternative Book)",
            author="Different Author",
            year=2000,
            provider="openlibrary",
            confidence=0.84,  # Below 0.85 threshold!
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: provider)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=registry, cache=mock_cache)
    result = identifier.identify(
        title="Dune (Original)",
        author="Frank Herbert (Original)",
        has_local_tags=True,
    )

    assert result.title == "Dune (Original)"
    assert result.author == "Frank Herbert (Original)"
    assert result.provider == "local_tag"
    assert result.confidence == 0.75


def test_partial_enrichment_in_confidence_window(mock_cache: MetadataCache):
    provider = MagicMock()
    provider.provider_name = "openlibrary"
    provider.search.return_value = [
        MetadataMatch(
            title="Dune (Variant)",
            author="Frank Herbert (Variant)",
            year=1965,
            narrator="George Guidall",
            series="Dune Chronicles",
            volume="1",
            provider="openlibrary",
            confidence=0.78,  # In [0.60, 0.85) window
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: provider)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=registry, cache=mock_cache)
    result = identifier.identify(
        title="Dune",
        author="Frank Herbert",
        has_local_tags=True,
    )

    # Local title & author preserved
    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    # Secondary attributes adopted
    assert result.narrator == "George Guidall"
    assert result.series == "Dune Chronicles"
    assert result.volume == "1"
    assert result.year == 1965
    assert result.provider == "local_tag"


def test_low_confidence_below_sixty_completely_rejected(mock_cache: MetadataCache):
    provider = MagicMock()
    provider.provider_name = "openlibrary"
    provider.search.return_value = [
        MetadataMatch(
            title="Completely Unrelated Book",
            author="Unrelated Author",
            narrator="Bogus Narrator",
            series="Bogus Series",
            provider="openlibrary",
            confidence=0.45,  # Below 0.60
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: provider)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=registry, cache=mock_cache)
    result = identifier.identify(
        title="Dune",
        author="Frank Herbert",
        has_local_tags=True,
    )

    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    assert result.narrator is None
    assert result.series is None
    assert result.provider == "local_tag"
    assert result.confidence == 0.75

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
    return MetadataCache(cache_file=tmp_path / "cache.json")


def test_cascade_stops_when_primary_provider_succeeds(mock_cache: MetadataCache):
    provider_ol = MagicMock()
    provider_ol.provider_name = "openlibrary"
    provider_ol.search.return_value = [
        MetadataMatch(
            title="Dune",
            author="Frank Herbert",
            provider="openlibrary",
            confidence=0.95,
        )
    ]

    provider_aud = MagicMock()
    provider_aud.provider_name = "audnexus"

    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: provider_ol)
    registry.register("audnexus", lambda **kw: provider_aud)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            ),
            "audnexus": ExternalProviderConfig(provider_name="audnexus", enabled=True, priority=20),
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=registry, cache=mock_cache)
    result = identifier.identify(title="Dune", author="Frank Herbert", has_local_tags=True)

    assert result.provider == "openlibrary"
    assert result.confidence == 0.95
    assert provider_ol.search.call_count == 1
    # Secondary provider must NOT be queried
    provider_aud.search.assert_not_called()


def test_cascade_falls_back_to_secondary_when_primary_confidence_is_low(mock_cache: MetadataCache):
    provider_ol = MagicMock()
    provider_ol.provider_name = "openlibrary"
    provider_ol.search.return_value = [
        MetadataMatch(
            title="Dune (Ambiguous)",
            author="Different Author",
            provider="openlibrary",
            confidence=0.65,
        )
    ]

    provider_aud = MagicMock()
    provider_aud.provider_name = "audnexus"
    provider_aud.search.return_value = [
        MetadataMatch(
            title="Dune",
            author="Frank Herbert",
            narrator="George Guidall",
            provider="audnexus",
            confidence=0.96,
        )
    ]

    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: provider_ol)
    registry.register("audnexus", lambda **kw: provider_aud)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            ),
            "audnexus": ExternalProviderConfig(provider_name="audnexus", enabled=True, priority=20),
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=registry, cache=mock_cache)
    result = identifier.identify(title="Dune", author="Frank Herbert", has_local_tags=True)

    assert result.provider == "audnexus"
    assert result.confidence == 0.96
    assert result.narrator == "George Guidall"
    assert provider_ol.search.call_count == 1
    assert provider_aud.search.call_count == 1


def test_cascade_falls_back_when_primary_provider_errors(mock_cache: MetadataCache):
    provider_ol = MagicMock()
    provider_ol.provider_name = "openlibrary"
    provider_ol.search.side_effect = ProviderTimeoutError("OL timed out")

    provider_aud = MagicMock()
    provider_aud.provider_name = "audnexus"
    provider_aud.search.return_value = [
        MetadataMatch(
            title="The Hobbit",
            author="J.R.R. Tolkien",
            provider="audnexus",
            confidence=0.92,
        )
    ]

    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: provider_ol)
    registry.register("audnexus", lambda **kw: provider_aud)

    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            ),
            "audnexus": ExternalProviderConfig(provider_name="audnexus", enabled=True, priority=20),
        },
    )

    identifier = AudiobookIdentifier(config=config, registry=registry, cache=mock_cache)
    result = identifier.identify(title="The Hobbit", author="J.R.R. Tolkien", has_local_tags=True)

    assert result.provider == "audnexus"
    assert result.confidence == 0.92
    assert provider_ol.search.call_count == 1
    assert provider_aud.search.call_count == 1

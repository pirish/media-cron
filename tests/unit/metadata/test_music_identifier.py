from pathlib import Path
from unittest.mock import MagicMock

from media_cron.config import MusicConfig
from media_cron.metadata.base import ProviderUnavailableError
from media_cron.metadata.cache import MusicMetadataCache
from media_cron.metadata.models import MusicCatalogMatch
from media_cron.metadata.music_identifier import MusicIdentifier


def test_music_identifier_cache_hit(tmp_path: Path):
    cache = MusicMetadataCache(cache_file=tmp_path / "cache.json")
    cached_match = MusicCatalogMatch(
        title="Animals",
        artist="Pink Floyd",
        release_id="mb-111",
        provider="musicbrainz",
        confidence=0.95,
        year=1977,
    )
    cache.put(provider="musicbrainz", artist="Pink Floyd", album="Animals", matches=[cached_match])

    mock_mb = MagicMock()
    identifier = MusicIdentifier(
        config=MusicConfig(enable_external_lookup=True),
        cache=cache,
        primary_provider=mock_mb,
    )

    match = identifier.identify(artist="Pink Floyd", album="Animals")
    assert match is not None
    assert match.release_id == "mb-111"
    # Provider was not called because cache had it
    mock_mb.search_release.assert_not_called()


def test_music_identifier_threshold_filtering(tmp_path: Path):
    cache = MusicMetadataCache(cache_file=tmp_path / "cache.json")
    low_confidence_match = MusicCatalogMatch(
        title="Some Other Album",
        artist="Other Artist",
        release_id="mb-222",
        provider="musicbrainz",
        confidence=0.60,
    )

    mock_mb = MagicMock()
    mock_mb.search_release.return_value = [low_confidence_match]

    identifier = MusicIdentifier(
        config=MusicConfig(enable_external_lookup=True, confidence_threshold=0.85),
        cache=cache,
        primary_provider=mock_mb,
    )

    # Low confidence should not be accepted
    match = identifier.identify(artist="Pink Floyd", album="Animals")
    assert match is None


def test_music_identifier_cascade_to_fallback(tmp_path: Path):
    cache = MusicMetadataCache(cache_file=tmp_path / "cache.json")

    mock_mb = MagicMock()
    mock_mb.search_release.side_effect = ProviderUnavailableError("Down")

    fallback_match = MusicCatalogMatch(
        title="Animals",
        artist="Pink Floyd",
        release_id="discogs-333",
        provider="discogs",
        confidence=0.90,
        year=1977,
    )
    mock_discogs = MagicMock()
    mock_discogs.search_release.return_value = [fallback_match]

    identifier = MusicIdentifier(
        config=MusicConfig(enable_external_lookup=True, confidence_threshold=0.85),
        cache=cache,
        primary_provider=mock_mb,
        fallback_provider=mock_discogs,
    )

    match = identifier.identify(artist="Pink Floyd", album="Animals")
    assert match is not None
    assert match.provider == "discogs"
    assert match.release_id == "discogs-333"


def test_music_identifier_offline_fallback(tmp_path: Path):
    cache = MusicMetadataCache(cache_file=tmp_path / "cache.json")

    mock_mb = MagicMock()
    mock_mb.search_release.side_effect = ProviderUnavailableError("Down")
    mock_discogs = MagicMock()
    mock_discogs.search_release.side_effect = ProviderUnavailableError("Down")

    identifier = MusicIdentifier(
        config=MusicConfig(enable_external_lookup=True),
        cache=cache,
        primary_provider=mock_mb,
        fallback_provider=mock_discogs,
    )

    # Graceful fallback without crashing
    match = identifier.identify(artist="Pink Floyd", album="Animals")
    assert match is None

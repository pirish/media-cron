import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from media_cron.metadata.base import (
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from media_cron.metadata.providers.musicbrainz import MusicBrainzProvider


@pytest.fixture
def mock_mb_response():
    return {
        "releases": [
            {
                "id": "mb-rel-111",
                "title": "Animals",
                "artist-credit": [{"name": "Pink Floyd"}],
                "date": "1977-01-23",
                "track-count": 5,
                "media": [
                    {
                        "tracks": [
                            {"title": "Pigs on the Wing 1"},
                            {"title": "Dogs"},
                            {"title": "Pigs (Three Different Ones)"},
                            {"title": "Sheep"},
                            {"title": "Pigs on the Wing 2"},
                        ]
                    }
                ],
            }
        ]
    }


def test_musicbrainz_search_success(mock_mb_response):
    provider = MusicBrainzProvider(min_delay_seconds=0.0)
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_mb_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        matches = provider.search_release("Pink Floyd", "Animals", track_count=5, year=1977)

        assert len(matches) >= 1
        top = matches[0]
        assert top.release_id == "mb-rel-111"
        assert top.title == "Animals"
        assert top.artist == "Pink Floyd"
        assert top.year == 1977
        assert top.track_count == 5
        assert len(top.tracks) == 5
        assert top.confidence >= 0.90


def test_musicbrainz_http_429_rate_limit():
    provider = MusicBrainzProvider(min_delay_seconds=0.0)
    err = urllib.error.HTTPError("https://musicbrainz.org", 429, "Too Many Requests", {}, None)

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderRateLimitError):
            provider.search_release("Pink Floyd", "Animals")


def test_musicbrainz_http_503_unavailable():
    provider = MusicBrainzProvider(min_delay_seconds=0.0)
    err = urllib.error.HTTPError("https://musicbrainz.org", 503, "Service Unavailable", {}, None)

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderUnavailableError):
            provider.search_release("Pink Floyd", "Animals")


def test_musicbrainz_timeout():
    provider = MusicBrainzProvider(min_delay_seconds=0.0)
    err = TimeoutError("Request timed out")

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderTimeoutError):
            provider.search_release("Pink Floyd", "Animals")

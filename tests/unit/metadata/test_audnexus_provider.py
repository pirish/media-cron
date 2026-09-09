import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from media_cron.metadata.base import (
    MetadataProviderProtocol,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from media_cron.metadata.providers.audnexus import AudnexusProvider


@pytest.fixture
def provider() -> AudnexusProvider:
    return AudnexusProvider()


def test_audnexus_implements_protocol(provider: AudnexusProvider):
    assert isinstance(provider, MetadataProviderProtocol)
    assert provider.provider_name == "audnexus"


def test_audnexus_build_url(provider: AudnexusProvider):
    url = provider._build_url("Dune", "Frank Herbert", "https://api.audnexus.com")
    assert url.startswith("https://api.audnexus.com/books?")
    assert "title=Dune" in url
    assert "author=Frank+Herbert" in url


def test_audnexus_parse_success(provider: AudnexusProvider):
    payload = [
        {
            "asin": "B002V1OF70",
            "title": "The Way of Kings",
            "authors": [{"name": "Brandon Sanderson"}],
            "narrators": [{"name": "Michael Kramer"}, {"name": "Kate Reading"}],
            "series": [{"name": "The Stormlight Archive", "position": "1"}],
            "releaseDate": "2010-08-31T00:00:00.000Z",
            "summary": "Roshar is a world of stone and storms.",
        }
    ]

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        matches = provider.search("The Way of Kings", "Brandon Sanderson")

    assert len(matches) == 1
    match = matches[0]
    assert match.title == "The Way of Kings"
    assert match.author == "Brandon Sanderson"
    assert match.narrator == "Michael Kramer, Kate Reading"
    assert match.series == "The Stormlight Archive"
    assert match.volume == "1"
    assert match.year == 2010
    assert match.work_id == "B002V1OF70"
    assert match.provider == "audnexus"
    assert match.confidence >= 0.90


def test_audnexus_rate_limit_error(provider: AudnexusProvider):
    err = urllib.error.HTTPError(
        url="https://api.audnexus.com/books",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderRateLimitError, match="rate limit exceeded"):
            provider.search("Dune", "Frank Herbert")


def test_audnexus_timeout_error(provider: AudnexusProvider):
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        with pytest.raises(ProviderTimeoutError, match="timed out"):
            provider.search("Dune", "Frank Herbert")


def test_audnexus_server_error(provider: AudnexusProvider):
    err = urllib.error.HTTPError(
        url="https://api.audnexus.com/books",
        code=503,
        msg="Service Unavailable",
        hdrs={},
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderUnavailableError, match="server error"):
            provider.search("Dune", "Frank Herbert")

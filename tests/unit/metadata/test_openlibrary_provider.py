import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from media_cron.metadata.base import (
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from media_cron.metadata.providers.openlibrary import OpenLibraryProvider


def test_openlibrary_build_url():
    provider = OpenLibraryProvider()
    url = provider._build_url("The Hobbit", "J.R.R. Tolkien", "https://openlibrary.org")
    assert "openlibrary.org/search.json" in url
    assert "title=The+Hobbit" in url or "title=The%20Hobbit" in url
    assert "author=J.R.R.+Tolkien" in url or "author=J.R.R.%20Tolkien" in url


def test_openlibrary_successful_search():
    provider = OpenLibraryProvider()
    fake_response = {
        "docs": [
            {
                "title": "The Hobbit",
                "author_name": ["J.R.R. Tolkien"],
                "first_publish_year": 1937,
                "key": "/works/OL262758W",
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        matches = provider.search(title="The Hobbit", author="J.R.R. Tolkien")
        assert len(matches) == 1
        m = matches[0]
        assert m.title == "The Hobbit"
        assert m.author == "J.R.R. Tolkien"
        assert m.year == 1937
        assert m.work_id == "/works/OL262758W"
        assert m.provider == "openlibrary"
        assert m.confidence >= 0.85


def test_openlibrary_empty_docs():
    provider = OpenLibraryProvider()
    fake_response = {"docs": []}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        matches = provider.search(title="Nonexistent Book Title 12345678")
        assert matches == []


def test_openlibrary_rate_limit():
    provider = OpenLibraryProvider()
    err = urllib.error.HTTPError(
        url="https://openlibrary.org",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=io.BytesIO(b"Rate limit exceeded"),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderRateLimitError):
            provider.search(title="Any Book")


def test_openlibrary_timeout():
    provider = OpenLibraryProvider()
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        with pytest.raises(ProviderTimeoutError):
            provider.search(title="Any Book")


def test_openlibrary_unavailable():
    provider = OpenLibraryProvider()
    err = urllib.error.URLError("DNS lookup failed")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderUnavailableError):
            provider.search(title="Any Book")

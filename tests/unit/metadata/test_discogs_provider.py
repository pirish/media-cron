import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from media_cron.metadata.base import ProviderUnavailableError
from media_cron.metadata.providers.discogs import DiscogsProvider


@pytest.fixture
def mock_discogs_response():
    return {
        "results": [
            {
                "id": 98765,
                "title": "Radiohead - OK Computer",
                "year": "1997",
                "country": "UK",
            }
        ]
    }


def test_discogs_search_with_token(mock_discogs_response):
    provider = DiscogsProvider(token="test-secret-token")
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_discogs_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        matches = provider.search_release("Radiohead", "OK Computer", year=1997)

        assert len(matches) >= 1
        top = matches[0]
        assert top.release_id == "98765"
        assert top.title == "OK Computer"
        assert top.artist == "Radiohead"
        assert top.year == 1997
        assert top.confidence >= 0.85

        req = mock_urlopen.call_args[0][0]
        auth_header = req.get_header("Authorization")
        assert auth_header == "Discogs token=test-secret-token"


def test_discogs_http_error():
    provider = DiscogsProvider(token="invalid-token")
    err = urllib.error.HTTPError("https://api.discogs.com", 500, "Internal Server Error", {}, None)

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderUnavailableError):
            provider.search_release("Radiohead", "OK Computer")

import urllib.parse
import urllib.request

from media_cron.metadata.media_servers.base import BaseMediaServerClient
from media_cron.metadata.models import MediaServerConfig


class PlexClient(BaseMediaServerClient):
    """Plex media server library rescan client."""

    @property
    def server_type(self) -> str:
        return "plex"

    def _build_request(
        self,
        config: MediaServerConfig,
        library_id: str | None = None,
        path: str | None = None,
    ) -> urllib.request.Request:
        base_url = config.url.rstrip("/")
        if library_id:
            endpoint = f"{base_url}/library/sections/{library_id}/refresh"
        else:
            endpoint = f"{base_url}/library/sections/all/refresh"

        if path:
            encoded_path = urllib.parse.quote(path, safe="")
            endpoint = f"{endpoint}?path={encoded_path}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "media-cron/0.1.0",
        }
        if config.token:
            headers["X-Plex-Token"] = config.token

        return urllib.request.Request(
            url=endpoint,
            headers=headers,
            method="GET",
        )

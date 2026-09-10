import urllib.request

from media_cron.metadata.media_servers.base import BaseMediaServerClient
from media_cron.metadata.models import MediaServerConfig


class EmbyClient(BaseMediaServerClient):
    """Emby media server library rescan client."""

    @property
    def server_type(self) -> str:
        return "emby"

    def _build_request(
        self,
        config: MediaServerConfig,
        library_id: str | None = None,
        path: str | None = None,
    ) -> urllib.request.Request:
        base_url = config.url.rstrip("/")
        if library_id:
            endpoint = f"{base_url}/Items/{library_id}/Refresh"
        else:
            endpoint = f"{base_url}/Library/Refresh"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "media-cron/0.1.0",
        }
        if config.token:
            headers["X-Emby-Token"] = config.token

        return urllib.request.Request(
            url=endpoint,
            data=b"{}",
            headers=headers,
            method="POST",
        )

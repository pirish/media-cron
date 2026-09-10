# Contract: Media Server Client Interface (Jellyfin, Emby, Plex)

**Feature**: `006-video-organization`  
**Date**: 2026-09-09  
**Status**: Complete  

---

## 1. Protocol Definition

Defines the contract for notifying media servers to perform library rescans:

```python
from typing import Protocol
from media_cron.metadata.models import MediaServerConfig, MediaServerRescanResult


class MediaServerClientProtocol(Protocol):
    """Protocol for media player/server library rescan notifications."""

    @property
    def server_type(self) -> str:
        """Returns the media server identifier: 'jellyfin', 'emby', or 'plex'."""
        ...

    def trigger_rescan(
        self,
        config: MediaServerConfig,
        library_id: str | None = None,
        path: str | None = None,
        dry_run: bool = False,
    ) -> MediaServerRescanResult:
        """Dispatches an authenticated HTTP rescan request to the media server."""
        ...
```

---

## 2. Server Specific Adapters

### Jellyfin Adapter
- **Endpoint**:
  - Global: `{config.url.rstrip('/')}/Library/Refresh`
  - Selective: `{config.url.rstrip('/')}/Items/{library_id}/Refresh` if `library_id` supplied
- **Method**: `POST`
- **Headers**:
  ```http
  X-Emby-Token: <config.token>
  Content-Type: application/json
  User-Agent: media-cron/0.1.0
  ```

### Emby Adapter
- **Endpoint**:
  - Global: `{config.url.rstrip('/')}/Library/Refresh`
  - Selective: `{config.url.rstrip('/')}/Items/{library_id}/Refresh` if `library_id` supplied
- **Method**: `POST`
- **Headers**:
  ```http
  X-Emby-Token: <config.token>
  Content-Type: application/json
  User-Agent: media-cron/0.1.0
  ```

### Plex Adapter
- **Endpoint**:
  - Global: `{config.url.rstrip('/')}/library/sections/all/refresh`
  - Selective: `{config.url.rstrip('/')}/library/sections/{library_id}/refresh` (with optional `?path={encoded_path}`)
- **Method**: `GET`
- **Headers**:
  ```http
  X-Plex-Token: <config.token>
  Accept: application/json
  User-Agent: media-cron/0.1.0
  ```

---

## 3. Resilience and Error Handling Contract

- **Timeout**: Strict timeout (default: 5.0 seconds).
- **Retry Policy**: Default single-shot attempt (`max_retries = 0`). When `config.max_retries > 0`, the client retries failed attempts with short backoff (e.g. 0.5s, 1.0s) up to `max_retries` times before declaring failure.
- **Non-Fatal**: If `urllib.error.HTTPError`, `urllib.error.URLError`, socket timeout, or retry exhaustion occurs:
  - Return `MediaServerRescanResult(success=False, error=str(err), status_code=getattr(err, 'code', None))`
  - Log warning via `logging.getLogger(__name__).warning(...)`
  - Never raise unhandled exceptions to caller.

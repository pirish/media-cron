# Research & Architectural Decisions: Torrent Client Integration

**Branch**: `002-torrent-client-integration` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

## Summary of Architectural Evaluations

This document records the technical evaluations, protocol research, and design decisions for integrating torrent clients into media-cron's pluggable ingestion and seeding pipeline.

---

## 1. Torrent Client HTTP/RPC Communication Stack

### Decision
Use Python's standard library `urllib.request` with `http.cookiejar.CookieJar` for HTTP/API client interactions.

### Rationale
- **Zero External Dependencies**: Adheres to Constitution Principle I (Library-First) and Principle V (Container-Native) by eliminating external networking dependencies.
- **Session Management**: `urllib.request.HTTPCookieProcessor` coupled with `http.cookiejar.CookieJar` automatically maintains the authenticated session cookie (`SID` for qBittorrent) across requests.
- **Timeout & Error Resilience**: `urllib.request` supports explicit socket timeouts on every request and provides structured exceptions (`URLError`, `HTTPError`) that map cleanly to deterministic exit codes.
- **Payload Handling**: Standard `json` library handles serialization and deserialization of API responses.

### Alternatives Considered
- `requests`: High-level and ergonomic, but introduces multiple external dependencies (`urllib3`, `certifi`, `idna`, `charset-normalizer`).
- `httpx`: Supports async/sync and HTTP/2, but excessive complexity for CLI batch and cron execution.
- Third-party client wrappers (`qbittorrent-api`): Tied specifically to qBittorrent and does not provide the unified abstraction required to plug in Transmission and Deluge.

---

## 2. qBittorrent Web API v2 Integration Specification

### Decision
Implement direct communication against qBittorrent Web API v2 endpoints:
1. **Authentication**: `POST /api/v2/auth/login` (form data: `username`, `password`). Stores `SID` cookie.
2. **List Torrents**: `GET /api/v2/torrents/info?filter=completed` (optional query parameters: `category`, `tag`).
3. **Torrent Files**: `GET /api/v2/torrents/files?hash=<info_hash>`.
4. **Relocate Storage**: `POST /api/v2/torrents/setLocation` (form data: `hashes=<info_hash>`, `location=<target_path>`).
5. **Tag Management**: `POST /api/v2/torrents/addTags` (form data: `hashes=<info_hash>`, `tags=<tag>`).
6. **Category Management**: `POST /api/v2/torrents/setCategory` (form data: `hashes=<info_hash>`, `category=<category>`).
7. **Torrent Control**: `POST /api/v2/torrents/pause` (form data: `hashes=<info_hash>`).

### Rationale
- Web API v2 is the standard API for all modern qBittorrent versions (v4.1.0+).
- Provides atomic `setLocation` which relocates storage on disk and updates the client's internal fastresume database without needing manual rechecks.
- Tagging and category updates are native operations that execute instantaneously.

### Alternatives Considered
- Web API v1: Deprecated and removed in current qBittorrent versions.
- Direct filesystem manipulation only: Leaves torrent client fastresume out of sync, causing broken torrents or missing payload errors.

---

## 3. Pluggable Torrent Client Abstraction (Transmission & Deluge)

### Decision
Define a `TorrentClientProtocol` in `media_cron.torrent.base` and a client registry `TorrentClientRegistry`:

```python
class TorrentClientProtocol(Protocol):
    def authenticate(self) -> bool: ...
    def list_completed_torrents(self, category: str | None = None, tag: str | None = None) -> list[TorrentItem]: ...
    def get_torrent(self, identifier: str) -> TorrentItem | None: ...
    def relocate_storage(self, info_hash: str, new_path: Path) -> bool: ...
    def apply_completion_state(self, info_hash: str, tag: str, category: str, pause: bool = False) -> bool: ...
```

### Rationale
- Supports first-class out-of-the-box `QBittorrentClient`.
- Enables seamless implementation of `TransmissionClient` (using Transmission's JSON-RPC spec: `torrent-get`, `torrent-set-location`, `torrent-set`) and `DelugeClient` (using Deluge's Web JSON-RPC) without altering any pipeline code.
- Testable via mock client implementations without requiring running torrent daemons in CI.

---

## 4. Path Mapping Engine (Container & Remote Filesystems)

### Decision
Implement a declarative `PathMappingRule` model:
- Replaces remote storage prefixes (as reported by the torrent client) with local storage prefixes (as mounted into media-cron).
- Example: Remote `/data/completed/` -> Local `/mnt/storage/downloads/`.
- Path translation is applied to `TorrentItem.content_path` and file listing paths before staging copies are initiated.

### Rationale
- Essential for Docker/Podman environments where qBittorrent and media-cron run in separate containers with different mount points.
- Simple, deterministic string prefix replacement with POSIX path resolution.

---

## 5. Ingestion Isolation Strategy (Clarification Q1)

### Decision
Always perform a full copy (`shutil.copy2`) of completed torrent payloads from the torrent client storage path into `staging_dir`.

### Rationale
- Preserves 100% isolation of the active download/seeding payload.
- Prevents file locking issues, partial write hazards, and torrent client disruption during media sanitization and organization.
- Adheres to the user decision recorded in Clarification Q1.

---

## 6. Clutter & Seeding Retention Strategy (Clarification Q3 & Q2)

### Decision
- When relocating torrents via the client API (`setLocation`), the client moves the entire release directory (including `.nfo`, sample clips, and release notes) to the configured target relocation directory (`seed_dir` or destination library).
- The clutter files are left intact in the seeding path to ensure tracker hash checks pass at 100%.
- The organization pipeline (from Feature 001) processes files from `staging_dir`, filtering out junk files when transferring to the organized library.

---

## 7. Dual State Idempotency Strategy (Clarification Q5)

### Decision
Upon successful pipeline processing:
1. Add completion tag: `media-cron-processed` (or user configured tag).
2. Set post-processing category: `media-cron-done` (or user configured category).
3. The ingestion scanner filters out any torrent possessing either the completion tag or the post-processing category.

### Rationale
- Prevents re-ingestion during automated recurring cron runs.
- Dual update ensures both tag-based and category-based client filters accurately reflect processed state.

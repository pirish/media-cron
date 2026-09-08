import http.cookiejar
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from media_cron.torrent.models import (
    TorrentClientConfig,
    TorrentFile,
    TorrentItem,
    TorrentState,
)

logger = logging.getLogger(__name__)


class QBittorrentClient:
    """Client adapter for qBittorrent Web API v2."""

    def __init__(self, config: TorrentClientConfig):
        self.config = config
        scheme = "https" if config.use_ssl else "http"
        self.base_url = f"{scheme}://{config.host}:{config.port}"
        self.timeout = config.timeout

        # Persistent cookie jar for session maintenance
        self.cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self._authenticated = False

    @property
    def client_type(self) -> str:
        return "qbittorrent"

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict | None = None,
    ) -> bytes:
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        req_data = None
        headers = {"User-Agent": "media-cron/1.0"}

        if data is not None:
            req_data = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        with self._opener.open(req, timeout=self.timeout) as resp:
            return resp.read()

    def authenticate(self) -> bool:
        """Authenticates with qBittorrent Web API v2."""
        if not self.config.username and not self.config.password:
            try:
                self._request("/api/v2/app/version")
                self._authenticated = True
                return True
            except Exception:
                self._authenticated = False
                return False

        login_data = {
            "username": self.config.username or "",
            "password": self.config.password or "",
        }

        try:
            resp_body = self._request("/api/v2/auth/login", method="POST", data=login_data)
            text = resp_body.decode("utf-8", errors="replace").strip()
            if text == "Ok.":
                self._authenticated = True
                return True
            logger.warning("qBittorrent login rejected: %s", text)
            self._authenticated = False
            return False
        except (urllib.error.URLError, TimeoutError) as e:
            logger.error("Failed to connect to qBittorrent at %s: %s", self.base_url, e)
            self._authenticated = False
            return False

    def test_connection(self) -> bool:
        """Validates connectivity and authentication."""
        return self.authenticate()

    def _map_state(self, raw_state: str) -> TorrentState:
        s = raw_state.lower()
        if s in ("uploading", "stalledup", "forcedup", "queuedup"):
            return TorrentState.SEEDING
        if s in ("completed", "pausedup"):
            return TorrentState.COMPLETED
        if s in ("downloading", "stalleddl", "forceddl", "queueddl"):
            return TorrentState.DOWNLOADING
        if s in ("pauseddl",):
            return TorrentState.PAUSED
        if s in ("checkingup", "checkingdl", "checkingresumedata"):
            return TorrentState.CHECKING
        if s in ("error", "missingfiles"):
            return TorrentState.ERROR
        return TorrentState.UNKNOWN

    def list_completed_torrents(
        self,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        exclude_categories: list[str] | None = None,
    ) -> list[TorrentItem]:
        """Queries qBittorrent for completed torrents matching filter criteria."""
        if not self._authenticated:
            if not self.test_connection():
                logger.error("Cannot list torrents: qBittorrent authentication failed.")
                return []
            self._authenticated = True

        try:
            body = self._request("/api/v2/torrents/info?filter=completed")
            raw_torrents = json.loads(body.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to fetch torrent list from qBittorrent: %s", e)
            return []

        filter_cfg = self.config.filters
        seeding_cfg = self.config.seeding
        # Apply query parameter overrides if supplied
        effective_categories = categories if categories is not None else filter_cfg.categories
        effective_tags = tags if tags is not None else filter_cfg.tags
        effective_exclude_tags = list(
            exclude_tags if exclude_tags is not None else filter_cfg.exclude_tags
        )
        effective_exclude_cats = list(
            exclude_categories if exclude_categories is not None else filter_cfg.exclude_categories
        )
        if seeding_cfg.completion_tag and seeding_cfg.completion_tag not in effective_exclude_tags:
            effective_exclude_tags.append(seeding_cfg.completion_tag)
        if (
            seeding_cfg.completion_category
            and seeding_cfg.completion_category not in effective_exclude_cats
        ):
            effective_exclude_cats.append(seeding_cfg.completion_category)

        results: list[TorrentItem] = []
        for item in raw_torrents:
            raw_tags = [t.strip() for t in item.get("tags", "").split(",") if t.strip()]
            torrent = TorrentItem(
                info_hash=item.get("hash", ""),
                name=item.get("name", ""),
                total_size=item.get("size", item.get("total_size", 0)),
                progress=float(item.get("progress", 0.0)),
                state=self._map_state(item.get("state", "")),
                save_path=item.get("save_path", ""),
                content_path=item.get("content_path", item.get("save_path", "")),
                category=item.get("category", ""),
                tags=raw_tags,
            )

            # Check eligibility
            if not torrent.is_completed() or not torrent.is_healthy():
                continue

            if effective_exclude_cats and torrent.category in effective_exclude_cats:
                continue

            if any(t in effective_exclude_tags for t in torrent.tags):
                continue

            if effective_categories and torrent.category not in effective_categories:
                continue

            if effective_tags and not any(t in torrent.tags for t in effective_tags):
                continue

            # Fetch file listing for completed torrent
            try:
                files_body = self._request(
                    f"/api/v2/torrents/files?hash={urllib.parse.quote(torrent.info_hash)}"
                )
                raw_files = json.loads(files_body.decode("utf-8"))
                torrent.files = [
                    TorrentFile(
                        name=f.get("name", ""),
                        size=f.get("size", 0),
                        progress=float(f.get("progress", 1.0)),
                    )
                    for f in raw_files
                ]
            except Exception as e:
                logger.warning("Could not fetch files for torrent %s: %s", torrent.info_hash, e)

            results.append(torrent)

        return results

    def get_torrent(self, identifier: str) -> TorrentItem | None:
        """Retrieves a single torrent by info-hash or name."""
        if not self._authenticated:
            if not self.test_connection():
                return None
            self._authenticated = True

        try:
            body = self._request("/api/v2/torrents/info")
            raw_torrents = json.loads(body.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to query torrents: %s", e)
            return None

        target = None
        ident_lower = identifier.lower()

        for item in raw_torrents:
            h = item.get("hash", "").lower()
            n = item.get("name", "")
            if h == ident_lower:
                target = item
                break
            if n == identifier and target is None:
                target = item

        if not target:
            return None

        raw_tags = [t.strip() for t in target.get("tags", "").split(",") if t.strip()]
        torrent = TorrentItem(
            info_hash=target.get("hash", ""),
            name=target.get("name", ""),
            total_size=target.get("size", target.get("total_size", 0)),
            progress=float(target.get("progress", 0.0)),
            state=self._map_state(target.get("state", "")),
            save_path=target.get("save_path", ""),
            content_path=target.get("content_path", target.get("save_path", "")),
            category=target.get("category", ""),
            tags=raw_tags,
        )

        try:
            files_body = self._request(
                f"/api/v2/torrents/files?hash={urllib.parse.quote(torrent.info_hash)}"
            )
            raw_files = json.loads(files_body.decode("utf-8"))
            torrent.files = [
                TorrentFile(
                    name=f.get("name", ""),
                    size=f.get("size", 0),
                    progress=float(f.get("progress", 1.0)),
                )
                for f in raw_files
            ]
        except Exception:
            pass

        return torrent

    def relocate_storage(self, info_hash: str, new_path: Path) -> bool:
        """Relocates torrent storage using qBittorrent setLocation API."""
        if not self._authenticated and not self.test_connection():
            return False

        try:
            data = {"hashes": info_hash, "location": str(new_path)}
            self._request("/api/v2/torrents/setLocation", method="POST", data=data)
            return True
        except Exception as e:
            logger.error("Failed to relocate torrent %s to %s: %s", info_hash, new_path, e)
            return False

    def add_tags(self, info_hash: str, tags: str) -> bool:
        """Adds tags to a torrent."""
        if not self._authenticated and not self.test_connection():
            return False
        try:
            self._request(
                "/api/v2/torrents/addTags",
                method="POST",
                data={"hashes": info_hash, "tags": tags},
            )
            return True
        except Exception as e:
            logger.error("Failed to add tags to torrent %s: %s", info_hash, e)
            return False

    def set_category(self, info_hash: str, category: str) -> bool:
        """Sets category on a torrent."""
        if not self._authenticated and not self.test_connection():
            return False
        try:
            self._request(
                "/api/v2/torrents/setCategory",
                method="POST",
                data={"hashes": info_hash, "category": category},
            )
            return True
        except Exception as e:
            logger.error("Failed to set category on torrent %s: %s", info_hash, e)
            return False

    def pause_torrent(self, info_hash: str) -> bool:
        """Pauses a torrent."""
        if not self._authenticated and not self.test_connection():
            return False
        try:
            self._request(
                "/api/v2/torrents/pause",
                method="POST",
                data={"hashes": info_hash},
            )
            return True
        except Exception as e:
            logger.error("Failed to pause torrent %s: %s", info_hash, e)
            return False

    def apply_completion_state(
        self,
        info_hash: str,
        tag: str,
        category: str,
        pause: bool = False,
    ) -> bool:
        """Applies completion tag and category, and optionally pauses the torrent."""
        if not self._authenticated and not self.test_connection():
            return False

        success = True
        if tag:
            if not self.add_tags(info_hash, tag):
                success = False

        if category:
            if not self.set_category(info_hash, category):
                success = False

        if pause:
            if not self.pause_torrent(info_hash):
                success = False

        return success
